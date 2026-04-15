from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from web3 import Web3

from app.evm.abi_erc20 import ERC20_ABI
from app.evm.abi_uniswap_v2_router import UNISWAP_V2_ROUTER_ABI
from app.evm.client import EvmChain, w3_for


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


def build_erc20_approve(
    chain: EvmChain,
    sender: str,
    token_address: str,
    spender: str,
    amount: int,
) -> BuiltTx:
    """Build an unsigned ERC-20 approve transaction."""
    w3 = w3_for(chain)
    checksum_sender = Web3.to_checksum_address(sender)
    checksum_token = Web3.to_checksum_address(token_address)
    checksum_spender = Web3.to_checksum_address(spender)
    token = w3.eth.contract(address=checksum_token, abi=ERC20_ABI)
    nonce = w3.eth.get_transaction_count(checksum_sender)
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
) -> BuiltTx:
    """Build an unsigned swapExactTokensForTokens transaction.

    The on-chain deadline is set to ``now + deadline_seconds`` at build time.
    If the user signs and broadcasts well after this call, the transaction may
    revert on-chain.  The frontend should re-call this endpoint close to
    submission time, or increase ``deadline_seconds`` to allow for signing
    latency.
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
    nonce = w3.eth.get_transaction_count(checksum_sender)
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
