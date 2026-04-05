from fastapi import APIRouter, Depends, HTTPException
from web3 import Web3

from app.security import get_current_user
from app.config import settings
from app.schemas import QuoteRequest, QuoteResponse, BuildRequest, BuildResponse, BuiltTxOut
from app.evm.client import EvmChain
from app.evm.tx_builder import (
    quote_uniswap_v2_amount_out,
    build_erc20_approve,
    build_uniswap_v2_swap_exact_tokens_for_tokens,
)
from app.bridge.bridge_adapter import BridgeStep, build_bridge_tx


router = APIRouter()


def _chains() -> tuple[EvmChain, EvmChain]:
    chain_a = EvmChain(chain_id=settings.chain_a_id, rpc_url=settings.rpc_chain_a, router=settings.router_chain_a)
    chain_b = EvmChain(chain_id=settings.chain_b_id, rpc_url=settings.rpc_chain_b, router=settings.router_chain_b)
    return chain_a, chain_b


def _slippage_min(amount_out: int, slippage_bps: int) -> int:
    return int(amount_out * (10_000 - slippage_bps) // 10_000)


@router.post("/quote", response_model=QuoteResponse)
def quote(req: QuoteRequest, user: str = Depends(get_current_user)):
    chain_a, chain_b = _chains()

    # Default simplistic paths: direct pair
    path_a = [req.chain_a_token_in, req.chain_a_token_out]
    path_b = [req.chain_b_token_in, req.chain_b_token_out]

    try:
        a_out, a_amounts = quote_uniswap_v2_amount_out(chain_a, req.amount_in, path_a)
        # The bridged amount is application-specific; we assume entire output from leg A is bridged into leg B input token.
        # In many designs, chain_a_token_out == chain_b_token_in (same asset via bridge).
        b_out, b_amounts = quote_uniswap_v2_amount_out(chain_b, a_out, path_b)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Quote failed: {e}")

    route = {
        "legA": {"chainId": chain_a.chain_id, "router": chain_a.router, "path": path_a, "amounts": a_amounts},
        "bridge": {"fromChainId": chain_a.chain_id, "toChainId": chain_b.chain_id, "token": req.chain_a_token_out, "amount": a_out},
        "legB": {"chainId": chain_b.chain_id, "router": chain_b.router, "path": path_b, "amounts": b_amounts},
    }

    return QuoteResponse(leg_a_amount_out=a_out, leg_b_amount_out=b_out, route=route)


@router.post("/build", response_model=BuildResponse)
def build(req: BuildRequest, user: str = Depends(get_current_user)):
    chain_a, chain_b = _chains()

    sender = Web3.to_checksum_address(req.sender_evm_address)
    recipient = Web3.to_checksum_address(req.recipient_evm_address)

    path_a = req.chain_a_path or [req.chain_a_token_in, req.chain_a_token_out]
    path_b = req.chain_b_path or [req.chain_b_token_in, req.chain_b_token_out]

    # 1) Quote to compute minOuts
    try:
        a_out, _ = quote_uniswap_v2_amount_out(chain_a, req.amount_in, path_a)
        a_min = _slippage_min(a_out, req.slippage_bps)

        # Bridge amount chosen by client; validate it is <= a_out
        if req.bridge_amount > a_out:
            raise HTTPException(status_code=400, detail="bridge_amount cannot exceed leg A quoted output")

        b_out, _ = quote_uniswap_v2_amount_out(chain_b, req.bridge_amount, path_b)
        b_min = _slippage_min(b_out, req.slippage_bps)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Build failed during quoting: {e}")

    unsigned = []
    notes = []

    # 2) Leg A approvals + swap (approve token_in for router)
    unsigned.append(
        BuiltTxOut(
            chain_id=chain_a.chain_id,
            kind="approve",
            tx=build_erc20_approve(chain_a, sender, req.chain_a_token_in, chain_a.router, req.amount_in).tx,
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
            ).tx,
        )
    )

    # 3) Bridge approval (approve bridge to move bridge_token) + bridge tx
    # NOTE: We don't know which bridge contract yet, so we can’t approve correctly.
    notes.append("Bridge tx builder is a stub: choose a bridge provider and implement build_bridge_tx + approvals.")
    bridge_step = BridgeStep(
        src_chain_id=chain_a.chain_id,
        dst_chain_id=chain_b.chain_id,
        token=req.bridge_token,
        amount=req.bridge_amount,
        recipient=recipient,
    )
    unsigned.append(
        BuiltTxOut(
            chain_id=chain_a.chain_id,
            kind="bridge",
            tx=build_bridge_tx(chain_a, sender, bridge_step).tx,
        )
    )

    # 4) Leg B approval + swap (on destination chain)
    unsigned.append(
        BuiltTxOut(
            chain_id=chain_b.chain_id,
            kind="approve",
            tx=build_erc20_approve(chain_b, sender, req.chain_b_token_in, chain_b.router, req.bridge_amount).tx,
        )
    )
    unsigned.append(
        BuiltTxOut(
            chain_id=chain_b.chain_id,
            kind="swap",
            tx=build_uniswap_v2_swap_exact_tokens_for_tokens(
                chain=chain_b,
                sender=sender,
                amount_in=req.bridge_amount,
                amount_out_min=b_min,
                path=path_b,
                recipient=recipient,
                deadline_seconds=settings.swap_deadline_seconds,
            ).tx,
        )
    )

    # Frontend must fill gas fields (maxFeePerGas, maxPriorityFeePerGas, gas) and correct nonces per chain.
    notes.append("Unsigned txs omit gas fields. Frontend wallet should estimate gas + set EIP-1559 fees.")
    notes.append("Nonces are fetched per-chain at build time; if user signs later, refresh nonces to avoid replacement/invalid nonce.")

    return BuildResponse(unsigned_txs=unsigned, notes=notes)f
