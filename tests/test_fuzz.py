"""
Fuzz / property-based tests for pure, network-free logic in the backend.

Uses Hypothesis to generate random valid (and edge-case) inputs and verifies
invariants that must hold regardless of the specific values.
"""

import pytest
from hypothesis import given, assume, settings as hyp_settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# _slippage_min  (copied inline so we can test without network)
# ---------------------------------------------------------------------------

def _slippage_min(amount_out: int, slippage_bps: int) -> int:
    """Fixed version: enforces a floor of 1 for non-zero outputs so that
    integer truncation can never produce amountOutMin = 0."""
    if amount_out == 0:
        return 0
    return max(1, int(amount_out * (10_000 - slippage_bps) // 10_000))


class TestSlippageMin:
    @given(
        amount_out=st.integers(min_value=1, max_value=10**30),
        slippage_bps=st.integers(min_value=1, max_value=2000),
    )
    def test_result_never_exceeds_amount_out(self, amount_out, slippage_bps):
        # Only meaningful for positive outputs; amount_out=0 is rejected upstream.
        result = _slippage_min(amount_out, slippage_bps)
        assert result <= amount_out

    @given(
        amount_out=st.integers(min_value=0, max_value=10**30),
        slippage_bps=st.integers(min_value=1, max_value=2000),
    )
    def test_result_non_negative(self, amount_out, slippage_bps):
        assert _slippage_min(amount_out, slippage_bps) >= 0

    @given(
        amount_out=st.integers(min_value=1, max_value=10**30),
        bps_lo=st.integers(min_value=1, max_value=1999),
    )
    def test_higher_slippage_gives_lower_or_equal_min(self, amount_out, bps_lo):
        bps_hi = bps_lo + 1
        assert _slippage_min(amount_out, bps_hi) <= _slippage_min(amount_out, bps_lo)

    @given(amount_out=st.integers(min_value=1, max_value=10**30))
    def test_zero_slippage_bps_would_return_full_amount(self, amount_out):
        # bps=0 is outside the schema-validated range but the math should hold
        # for positive amounts (amount_out=0 is rejected by routes before this is called)
        assert _slippage_min(amount_out, 0) == amount_out

    def test_zero_amount_out_returns_zero(self):
        # amount_out=0 always returns 0 (route rejects before slippage_min is called)
        assert _slippage_min(0, 50) == 0
        assert _slippage_min(0, 2000) == 0

    @given(
        amount_out=st.integers(min_value=1, max_value=10**30),
        slippage_bps=st.integers(min_value=1, max_value=2000),
    )
    def test_result_at_least_one_for_positive_amount(self, amount_out, slippage_bps):
        # No matter how small amount_out is, the floor prevents amountOutMin=0
        assert _slippage_min(amount_out, slippage_bps) >= 1


# ---------------------------------------------------------------------------
# Bridge fee helpers
# ---------------------------------------------------------------------------

def _bridge_fee_amount(amount: int, fee_bps: int) -> int:
    return int(amount * fee_bps // 10_000)

def _bridge_amount_received(amount: int, fee_bps: int) -> int:
    return amount - _bridge_fee_amount(amount, fee_bps)


class TestBridgeFeeHelpers:
    @given(
        amount=st.integers(min_value=0, max_value=10**30),
        fee_bps=st.integers(min_value=0, max_value=10_000),
    )
    def test_received_never_exceeds_amount(self, amount, fee_bps):
        assert _bridge_amount_received(amount, fee_bps) <= amount

    @given(
        amount=st.integers(min_value=0, max_value=10**30),
        fee_bps=st.integers(min_value=0, max_value=10_000),
    )
    def test_received_non_negative(self, amount, fee_bps):
        assert _bridge_amount_received(amount, fee_bps) >= 0

    @given(amount=st.integers(min_value=0, max_value=10**30))
    def test_zero_fee_is_identity(self, amount):
        assert _bridge_amount_received(amount, 0) == amount

    @given(amount=st.integers(min_value=0, max_value=10**30))
    def test_full_fee_yields_zero(self, amount):
        assert _bridge_amount_received(amount, 10_000) == 0

    @given(
        amount=st.integers(min_value=1, max_value=10**30),
        fee_lo=st.integers(min_value=0, max_value=9_999),
    )
    def test_higher_fee_gives_lower_or_equal_received(self, amount, fee_lo):
        fee_hi = fee_lo + 1
        assert _bridge_amount_received(amount, fee_hi) <= _bridge_amount_received(amount, fee_lo)


# ---------------------------------------------------------------------------
# Compound worst-case slippage
# ---------------------------------------------------------------------------

class TestCompoundSlippage:
    @given(
        b_out=st.integers(min_value=1, max_value=10**30),
        slippage_bps=st.integers(min_value=1, max_value=2000),
    )
    def test_worst_case_le_single_leg_min(self, b_out, slippage_bps):
        single_min = _slippage_min(b_out, slippage_bps)
        worst_case = _slippage_min(_slippage_min(b_out, slippage_bps), slippage_bps)
        assert worst_case <= single_min

    @given(
        b_out=st.integers(min_value=1, max_value=10**30),
        slippage_bps=st.integers(min_value=1, max_value=2000),
    )
    def test_worst_case_non_negative(self, b_out, slippage_bps):
        assert _slippage_min(_slippage_min(b_out, slippage_bps), slippage_bps) >= 0


# ---------------------------------------------------------------------------
# Schema validation – QuoteRequest / BuildRequest
# ---------------------------------------------------------------------------

from pydantic import ValidationError
from app.schemas import QuoteRequest, BuildRequest

ADDR = "0x" + "a" * 40  # dummy hex string (not checksum-validated by pydantic)


class TestQuoteRequestSchema:
    @given(slippage_bps=st.integers(min_value=1, max_value=2000))
    def test_valid_slippage_accepted(self, slippage_bps):
        req = QuoteRequest(
            chain_a_token_in=ADDR,
            chain_a_token_out=ADDR,
            amount_in=1000,
            chain_b_token_in=ADDR,
            chain_b_token_out=ADDR,
            slippage_bps=slippage_bps,
        )
        assert req.slippage_bps == slippage_bps

    @given(slippage_bps=st.one_of(st.integers(max_value=0), st.integers(min_value=2001)))
    def test_invalid_slippage_rejected(self, slippage_bps):
        with pytest.raises(ValidationError):
            QuoteRequest(
                chain_a_token_in=ADDR,
                chain_a_token_out=ADDR,
                amount_in=1000,
                chain_b_token_in=ADDR,
                chain_b_token_out=ADDR,
                slippage_bps=slippage_bps,
            )

    @given(amount_in=st.integers(min_value=1, max_value=10**30))
    def test_amount_in_roundtrips(self, amount_in):
        req = QuoteRequest(
            chain_a_token_in=ADDR,
            chain_a_token_out=ADDR,
            amount_in=amount_in,
            chain_b_token_in=ADDR,
            chain_b_token_out=ADDR,
        )
        assert req.amount_in == amount_in

    def test_amount_in_zero_rejected(self):
        with pytest.raises(ValidationError):
            QuoteRequest(
                chain_a_token_in=ADDR,
                chain_a_token_out=ADDR,
                amount_in=0,
                chain_b_token_in=ADDR,
                chain_b_token_out=ADDR,
            )


class TestBuildRequestSchema:
    @given(slippage_bps=st.integers(min_value=1, max_value=2000))
    def test_valid_slippage_accepted(self, slippage_bps):
        req = BuildRequest(
            sender_evm_address=ADDR,
            recipient_evm_address=ADDR,
            chain_a_token_in=ADDR,
            chain_a_token_out=ADDR,
            amount_in=1000,
            chain_b_token_in=ADDR,
            chain_b_token_out=ADDR,
            slippage_bps=slippage_bps,
            bridge_token=ADDR,
            bridge_amount=500,
        )
        assert req.slippage_bps == slippage_bps

    @given(
        amount_in=st.integers(min_value=1, max_value=10**18),
        bridge_amount=st.integers(min_value=1, max_value=10**18),
    )
    def test_bridge_amount_and_amount_in_independent(self, amount_in, bridge_amount):
        req = BuildRequest(
            sender_evm_address=ADDR,
            recipient_evm_address=ADDR,
            chain_a_token_in=ADDR,
            chain_a_token_out=ADDR,
            amount_in=amount_in,
            chain_b_token_in=ADDR,
            chain_b_token_out=ADDR,
            bridge_token=ADDR,
            bridge_amount=bridge_amount,
        )
        assert req.amount_in == amount_in
        assert req.bridge_amount == bridge_amount

    def test_amount_in_zero_rejected(self):
        with pytest.raises(ValidationError):
            BuildRequest(
                sender_evm_address=ADDR,
                recipient_evm_address=ADDR,
                chain_a_token_in=ADDR,
                chain_a_token_out=ADDR,
                amount_in=0,
                chain_b_token_in=ADDR,
                chain_b_token_out=ADDR,
                bridge_token=ADDR,
                bridge_amount=500,
            )

    def test_bridge_amount_zero_rejected(self):
        with pytest.raises(ValidationError):
            BuildRequest(
                sender_evm_address=ADDR,
                recipient_evm_address=ADDR,
                chain_a_token_in=ADDR,
                chain_a_token_out=ADDR,
                amount_in=1000,
                chain_b_token_in=ADDR,
                chain_b_token_out=ADDR,
                bridge_token=ADDR,
                bridge_amount=0,
            )


# ---------------------------------------------------------------------------
# Security – password hashing / JWT round-trip
# ---------------------------------------------------------------------------

from app.security import hash_password, verify_password, create_access_token
from jose import jwt
from app.config import settings


# bcrypt is intentionally slow; use simple unit tests rather than fuzz tests for hash/verify.
class TestPasswordHashing:
    def test_verify_own_hash(self):
        pw_hash = hash_password("correct-horse-battery-staple")
        assert verify_password("correct-horse-battery-staple", pw_hash) is True

    def test_wrong_password_not_verified(self):
        pw_hash = hash_password("secret")
        assert verify_password("wrong", pw_hash) is False


class TestJWT:
    @given(username=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N", "P"))))
    def test_token_decodes_to_same_subject(self, username):
        token = create_access_token(username)
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == username

    @given(username=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N", "P"))))
    def test_token_has_exp_and_iat(self, username):
        token = create_access_token(username)
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert "exp" in payload
        assert "iat" in payload
        assert payload["exp"] > payload["iat"]


# ---------------------------------------------------------------------------
# DB helpers – in-memory user store
# Bcrypt is intentionally slow; patch pwd_context with a fast scheme so we
# can exercise the registration/auth *logic* under fuzz without multi-second delays.
# ---------------------------------------------------------------------------

from unittest.mock import patch
from passlib.context import CryptContext
from app.db import create_user, authenticate, _USERS

_FAST_CTX = CryptContext(schemes=["md5_crypt"], deprecated="auto")


class TestDB:
    def setup_method(self):
        _USERS.clear()

    @given(
        username=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N"))),
        password=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
    )
    @hyp_settings(max_examples=50)
    def test_create_then_authenticate_succeeds(self, username, password):
        _USERS.clear()
        with patch("app.security.pwd_context", _FAST_CTX):
            create_user(username, password)
            assert authenticate(username, password) is True

    @given(
        username=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N"))),
        password=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
        wrong=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
    )
    @hyp_settings(max_examples=50)
    def test_wrong_password_rejected(self, username, password, wrong):
        assume(password != wrong)
        _USERS.clear()
        with patch("app.security.pwd_context", _FAST_CTX):
            create_user(username, password)
            assert authenticate(username, wrong) is False

    @given(
        username=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N"))),
        password=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
    )
    @hyp_settings(max_examples=50)
    def test_duplicate_registration_raises(self, username, password):
        _USERS.clear()
        with patch("app.security.pwd_context", _FAST_CTX):
            create_user(username, password)
            with pytest.raises(ValueError):
                create_user(username, password)

    @given(
        username=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N"))),
        password=st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
    )
    @hyp_settings(max_examples=50)
    def test_authenticate_unknown_user_returns_false(self, username, password):
        _USERS.clear()
        assert authenticate(username, password) is False
