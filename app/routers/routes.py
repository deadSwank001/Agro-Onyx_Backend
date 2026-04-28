from fastapi import APIRouter, Depends, HTTPException
from web3 import Web3

from app.security import get_current_user
from app.config import settings
from app.schemas import QuoteRequest, QuoteResponse, BuildRequest, BuildResponse, BuiltTxOut
from app.evm.client import EvmChain
from app.evm.tx_builder import (
    get_price_impact_bps,
    quote_uniswap_v2_amount_out,
    build_erc20_approve,
    build_uniswap_v2_swap_exact_tokens_for_tokens,
)
from app.bridge.bridge_adapter import BridgeStep, bridge_amount_received, build_bridge_tx


router = APIRouter()


def _chains() -> tuple[EvmChain, EvmChain]:
    chain_a = EvmChain(chain_id=settings.chain_a_id, rpc_url=settings.rpc_chain_a, router=settings.router_chain_a)
    chain_b = EvmChain(chain_id=settings.chain_b_id, rpc_url=settings.rpc_chain_b, router=settings.router_chain_b)
    return chain_a, chain_b


def _slippage_min(amount_out: int, slippage_bps: int) -> int:
    """Return the minimum acceptable output after applying slippage tolerance.

    Enforces a floor of 1 so that a tiny ``amount_out`` never silently yields
    ``amountOutMin = 0`` (which would remove all sandwich protection).
    Callers must separately reject swaps where ``amount_out`` itself is 0.
    """
    if amount_out == 0:
        return 0
    return max(1, int(amount_out * (10_000 - slippage_bps) // 10_000))


def _validate_common(amount_in: int, slippage_bps: int) -> None:
    """Raise HTTPException for inputs that violate global risk controls."""
    if amount_in > settings.max_amount_in:
        raise HTTPException(
            status_code=400,
            detail=(
                f"amount_in {amount_in} exceeds the maximum allowed trade size "
                f"({settings.max_amount_in}). Split into smaller orders."
            ),
        )
    if slippage_bps > settings.max_slippage_bps:
        raise HTTPException(
            status_code=400,
            detail=(
                f"slippage_bps {slippage_bps} exceeds the maximum allowed tolerance "
                f"({settings.max_slippage_bps} bps = {settings.max_slippage_bps / 100:.1f} %). "
                "Override MAX_SLIPPAGE_BPS env var to increase the limit."
            ),
        )


@router.post("/quote", response_model=QuoteResponse)
def quote(req: QuoteRequest, user: str = Depends(get_current_user)):
    _validate_common(req.amount_in, req.slippage_bps)

    chain_a, chain_b = _chains()

    # Default simplistic paths: direct pair
    path_a = [req.chain_a_token_in, req.chain_a_token_out]
    path_b = [req.chain_b_token_in, req.chain_b_token_out]

    try:
        a_out, a_amounts = quote_uniswap_v2_amount_out(chain_a, req.amount_in, path_a)
        if a_out == 0:
            raise HTTPException(status_code=400, detail="Leg A quote returned 0 output; pair may lack liquidity.")

        # Bridge fee reduces what arrives on chain B
        bridge_step_preview = BridgeStep(
            src_chain_id=chain_a.chain_id,
            dst_chain_id=chain_b.chain_id,
            token=req.chain_a_token_out,
            amount=a_out,
            bridge_fee_bps=settings.bridge_fee_bps,
        )
        b_in = bridge_amount_received(bridge_step_preview)
        if b_in <= 0:
            raise HTTPException(status_code=400, detail="Bridge fee consumes the entire leg A output.")

        b_out, b_amounts = quote_uniswap_v2_amount_out(chain_b, b_in, path_b)
        if b_out == 0:
            raise HTTPException(status_code=400, detail="Leg B quote returned 0 output; pair may lack liquidity.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Quote failed: {e}")

    # Price impact per leg (0 if factory not configured or path > 2 tokens)
    impact_a = get_price_impact_bps(chain_a, settings.factory_chain_a, req.amount_in, path_a, a_out)
    impact_b = get_price_impact_bps(chain_b, settings.factory_chain_b, b_in, path_b, b_out)

    # Conservative compound worst-case floor: apply slippage to b_out twice
    # (once for leg A degradation propagating through the bridge, once for leg B execution)
    worst_case = _slippage_min(_slippage_min(b_out, req.slippage_bps), req.slippage_bps)

    effective_rate = b_out / req.amount_in

    route = {
        "legA": {"chainId": chain_a.chain_id, "router": chain_a.router, "path": path_a, "amounts": a_amounts},
        "bridge": {
            "fromChainId": chain_a.chain_id,
            "toChainId": chain_b.chain_id,
            "token": req.chain_a_token_out,
            "amount": a_out,
            "feeAmount": bridge_step_preview.amount - b_in,
            "amountReceived": b_in,
        },
        "legB": {"chainId": chain_b.chain_id, "router": chain_b.router, "path": path_b, "amounts": b_amounts},
    }

    return QuoteResponse(
        leg_a_amount_out=a_out,
        leg_b_amount_out=b_out,
        route=route,
        worst_case_amount_out=worst_case,
        price_impact_a_bps=impact_a,
        price_impact_b_bps=impact_b,
        effective_rate=effective_rate,
    )


@router.post("/build", response_model=BuildResponse)
def build(req: BuildRequest, user: str = Depends(get_current_user)):
    _validate_common(req.amount_in, req.slippage_bps)

    chain_a, chain_b = _chains()

    sender = Web3.to_checksum_address(req.sender_evm_address)
    recipient = Web3.to_checksum_address(req.recipient_evm_address)

    path_a = req.chain_a_path or [req.chain_a_token_in, req.chain_a_token_out]
    path_b = req.chain_b_path or [req.chain_b_token_in, req.chain_b_token_out]

    # 1) Quote to compute minOuts and validate risk parameters
    try:
        a_out, _ = quote_uniswap_v2_amount_out(chain_a, req.amount_in, path_a)
        if a_out == 0:
            raise HTTPException(status_code=400, detail="Leg A quote returned 0 output; pair may lack liquidity.")

        a_min = _slippage_min(a_out, req.slippage_bps)

        # Bridge amount must be covered even under maximum leg A slippage
        if req.bridge_amount > a_min:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"bridge_amount ({req.bridge_amount}) exceeds the slippage-adjusted "
                    f"leg A minimum output ({a_min}). Reduce bridge_amount to account for "
                    f"leg A execution risk."
                ),
            )

        # Deduct bridge fee so leg B is quoted for what actually arrives
        bridge_step = BridgeStep(
            src_chain_id=chain_a.chain_id,
            dst_chain_id=chain_b.chain_id,
            token=req.bridge_token,
            amount=req.bridge_amount,
            recipient=recipient,
            bridge_fee_bps=settings.bridge_fee_bps,
        )
        b_in = bridge_amount_received(bridge_step)
        if b_in <= 0:
            raise HTTPException(status_code=400, detail="Bridge fee consumes the entire bridge_amount.")

        b_out, _ = quote_uniswap_v2_amount_out(chain_b, b_in, path_b)
        if b_out == 0:
            raise HTTPException(status_code=400, detail="Leg B quote returned 0 output; pair may lack liquidity.")

        b_min = _slippage_min(b_out, req.slippage_bps)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Build failed during quoting: {e}")

    # Price impact check – refuse to build if either leg's impact is too high
    impact_a = get_price_impact_bps(chain_a, settings.factory_chain_a, req.amount_in, path_a, a_out)
    impact_b = get_price_impact_bps(chain_b, settings.factory_chain_b, b_in, path_b, b_out)
    combined_impact = impact_a + impact_b
    if combined_impact > settings.max_price_impact_bps:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Combined price impact ({combined_impact} bps) exceeds the allowed maximum "
                f"({settings.max_price_impact_bps} bps). Use a smaller order or a deeper pool."
            ),
        )

    unsigned = []
    notes = []

    # 2) Leg A: approve (nonce+0) then swap (nonce+1)
    unsigned.append(
        BuiltTxOut(
            chain_id=chain_a.chain_id,
            kind="approve",
            tx=build_erc20_approve(
                chain_a, sender, req.chain_a_token_in, chain_a.router, req.amount_in,
                nonce_offset=0,
            ).tx,
        )
    )
    unsigned.append(
        BuiltTxOut(
            chain_id=chain_a.chain_id,
            kind="swap",
            tx=build_uniswap_v2_swap_exact_tokens_for_tokens(
                chain=chain_a,
                sender=sender,
                amount_in=req.amount_in,
                amount_out_min=a_min,
                path=path_a,
                recipient=sender,  # keep proceeds in sender before bridging
                deadline_seconds=settings.swap_deadline_seconds,
                nonce_offset=1,
            ).tx,
        )
    )

    # 3) Bridge: deposit (nonce+2 on chain_a)
    unsigned.append(
        BuiltTxOut(
            chain_id=chain_a.chain_id,
            kind="bridge",
            tx=build_bridge_tx(
                chain_src=chain_a,
                sender=sender,
                step=bridge_step,
                spoke_pool_address=settings.spoke_pool_chain_a,
                nonce_offset=2,
            ).tx,
        )
    )
    if settings.spoke_pool_chain_a == "0x0000000000000000000000000000000000000000":
        notes.append(
            "Bridge tx is a stub (SPOKE_POOL_CHAIN_A not set). "
            "Set the env var to the Across SpokePool address for your source chain."
        )

    # 4) Leg B: approve (nonce+0 on chain_b) then swap (nonce+1 on chain_b)
    # Use bridge_amount_received (b_in) so amounts match what actually arrives.
    unsigned.append(
        BuiltTxOut(
            chain_id=chain_b.chain_id,
            kind="approve",
            tx=build_erc20_approve(
                chain_b, sender, req.chain_b_token_in, chain_b.router, b_in,
                nonce_offset=0,
            ).tx,
        )
    )
    unsigned.append(
        BuiltTxOut(
            chain_id=chain_b.chain_id,
            kind="swap",
            tx=build_uniswap_v2_swap_exact_tokens_for_tokens(
                chain=chain_b,
                sender=sender,
                amount_in=b_in,
                amount_out_min=b_min,
                path=path_b,
                recipient=recipient,
                deadline_seconds=settings.swap_deadline_seconds,
                nonce_offset=1,
            ).tx,
        )
    )

    # Frontend must fill gas fields (maxFeePerGas, maxPriorityFeePerGas, gas) and correct nonces per chain.
    notes.append("Unsigned txs omit gas fields. Frontend wallet should estimate gas + set EIP-1559 fees.")
    notes.append("Nonces are fetched per-chain at build time; if user signs later, refresh nonces to avoid replacement/invalid nonce.")

    return BuildResponse(unsigned_txs=unsigned, notes=notes)
