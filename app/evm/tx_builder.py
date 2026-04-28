from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from web3 import Web3

from app.evm.abi_erc20 import ERC20_ABI
from app.evm.abi_uniswap_v2_factory import UNISWAP_V2_FACTORY_ABI
from app.evm.abi_uniswap_v2_pair import UNISWAP_V2_PAIR_ABI
from app.evm.abi_uniswap_v2_router import UNISWAP_V2_ROUTER_ABI
from app.evm.client import EvmChain, w3_for

_ZERO_ADDR = "0x0000000000000000000000000000000000000000"


@dataclass
class BuiltTx:
    chain_id: int
    tx: Dict[str, Any]


def quote_uniswap_v2_amount_out(
    chain: EvmChain,
    amount_in: int,
    path: List[str],
) -> Tuple[int, List[int]]:
    """Call getAmountsOut on the Uniswap V2 router; returns (final_amount_out, full_amounts_list)."""
    w3 = w3_for(chain)
    checksum_path = [Web3.to_checksum_address(t) for t in path]
    router = w3.eth.contract(
        address=Web3.to_checksum_address(chain.router),
        abi=UNISWAP_V2_ROUTER_ABI,
    )
    amounts: List[int] = router.functions.getAmountsOut(amount_in, checksum_path).call()
    return amounts[-1], list(amounts)


def get_price_impact_bps(
    chain: EvmChain,
    factory_address: str,
    amount_in: int,
    path: List[str],
    amount_out: int,
) -> int:
    """Return price impact for a direct (2-token) swap in basis points.

    Price impact is defined as ``(spot_out - actual_out) / spot_out * 10_000``
    where ``spot_out`` is computed from the pair reserves (no fee, no impact).

    Returns 0 for multi-hop paths or when reserves are unavailable so that
    callers can continue without crashing.
    """
    if len(path) != 2:
        return 0
    if factory_address == _ZERO_ADDR:
        return 0
    try:
        w3 = w3_for(chain)
        token_in = Web3.to_checksum_address(path[0])
        token_out_addr = Web3.to_checksum_address(path[1])

        factory = w3.eth.contract(
            address=Web3.to_checksum_address(factory_address),
            abi=UNISWAP_V2_FACTORY_ABI,
        )
        pair_address = factory.functions.getPair(token_in, token_out_addr).call()
        if pair_address == _ZERO_ADDR:
            return 0

        pair = w3.eth.contract(address=pair_address, abi=UNISWAP_V2_PAIR_ABI)
        reserves = pair.functions.getReserves().call()
        token0 = Web3.to_checksum_address(pair.functions.token0().call())

        if token0 == token_in:
            reserve_in, reserve_out = reserves[0], reserves[1]
        else:
            reserve_in, reserve_out = reserves[1], reserves[0]

        if reserve_in == 0 or reserve_out == 0:
            return 0

        # Spot output (no fees, no impact): amount_in * reserve_out / reserve_in
        spot_out = amount_in * reserve_out // reserve_in
        if spot_out == 0:
            return 0

        impact = max(0, (spot_out - amount_out) * 10_000 // spot_out)
        return impact
    except Exception:
        return 0


def build_erc20_approve(
    chain: EvmChain,
    sender: str,
    token_address: str,
    spender: str,
    amount: int,
    nonce_offset: int = 0,
) -> BuiltTx:
    """Build an unsigned ERC-20 approve transaction.

    ``nonce_offset`` is added to the on-chain pending nonce so that multiple
    transactions built in a single request have distinct, sequential nonces.
    """
    w3 = w3_for(chain)
    checksum_sender = Web3.to_checksum_address(sender)
    checksum_token = Web3.to_checksum_address(token_address)
    checksum_spender = Web3.to_checksum_address(spender)
    token = w3.eth.contract(address=checksum_token, abi=ERC20_ABI)
    nonce = w3.eth.get_transaction_count(checksum_sender) + nonce_offset
    tx = token.functions.approve(checksum_spender, amount).build_transaction(
        {
            "chainId": chain.chain_id,
            "from": checksum_sender,
            "nonce": nonce,
        }
    )
    return BuiltTx(chain_id=chain.chain_id, tx=tx)


def build_uniswap_v2_swap_exact_tokens_for_tokens(
    chain: EvmChain,
    sender: str,
    amount_in: int,
    amount_out_min: int,
    path: List[str],
    recipient: str,
    deadline_seconds: int = 1200,
    nonce_offset: int = 0,
) -> BuiltTx:
    """Build an unsigned swapExactTokensForTokens transaction.

    The on-chain deadline is set to ``now + deadline_seconds`` at build time.
    If the user signs and broadcasts well after this call, the transaction may
    revert on-chain.  The frontend should re-call this endpoint close to
    submission time, or increase ``deadline_seconds`` to allow for signing
    latency.

    ``nonce_offset`` is added to the on-chain pending nonce so that multiple
    transactions built in a single request have distinct, sequential nonces.
    """
    w3 = w3_for(chain)
    checksum_sender = Web3.to_checksum_address(sender)
    checksum_recipient = Web3.to_checksum_address(recipient)
    checksum_path = [Web3.to_checksum_address(t) for t in path]
    router = w3.eth.contract(
        address=Web3.to_checksum_address(chain.router),
        abi=UNISWAP_V2_ROUTER_ABI,
    )
    deadline = int(datetime.now(timezone.utc).timestamp()) + deadline_seconds
    nonce = w3.eth.get_transaction_count(checksum_sender) + nonce_offset
    tx = router.functions.swapExactTokensForTokens(
        amount_in,
        amount_out_min,
        checksum_path,
        checksum_recipient,
        deadline,
    ).build_transaction(
        {
            "chainId": chain.chain_id,
            "from": checksum_sender,
            "nonce": nonce,
        }
    )
    return BuiltTx(chain_id=chain.chain_id, tx=tx)
