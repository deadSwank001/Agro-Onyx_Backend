from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any

from web3 import Web3

from app.bridge.abi_across_spoke_pool import ACROSS_SPOKE_POOL_ABI
from app.evm.tx_builder import BuiltTx
from app.evm.client import EvmChain, w3_for

_ZERO_ADDR = "0x0000000000000000000000000000000000000000"


@dataclass
class BridgeStep:
    # A generic representation of what we intend to bridge.
    src_chain_id: int
    dst_chain_id: int
    token: str
    amount: int
    recipient: str
    # Provider fee charged on top of the bridged amount (basis points).
    # The recipient receives ``amount - bridge_fee_amount(step)`` tokens.
    bridge_fee_bps: int = field(default=0)


def bridge_fee_amount(step: BridgeStep) -> int:
    """Return the absolute fee deducted by the bridge provider."""
    return int(step.amount * step.bridge_fee_bps // 10_000)


def bridge_amount_received(step: BridgeStep) -> int:
    """Return the amount the recipient will actually receive after bridge fees."""
    return step.amount - bridge_fee_amount(step)


def build_bridge_tx(
    chain_src: EvmChain,
    sender: str,
    step: BridgeStep,
    spoke_pool_address: str = _ZERO_ADDR,
    nonce_offset: int = 0,
) -> BuiltTx:
    """Build an unsigned Across Protocol SpokePool deposit transaction.

    If ``spoke_pool_address`` is the zero address (i.e. not yet configured),
    a clearly-labelled stub placeholder is returned instead so that the rest
    of the build pipeline can still assemble the unsigned transaction list.

    ``nonce_offset`` is added to the on-chain pending nonce so that this tx
    lines up correctly after the approve + swap built on the same chain.

    The ``bridge_fee_bps`` stored on ``step`` is converted to Across'
    ``relayerFeePct`` which is an 18-decimal fixed-point integer
    (1 bps == 10 ** 14).
    """
    if spoke_pool_address == _ZERO_ADDR:
        # Spoke pool not yet configured – return a stub so callers don't crash.
        tx: Dict[str, Any] = {
            "chainId": chain_src.chain_id,
            "from": sender,
            "to": _ZERO_ADDR,
            "nonce": 0,
            "data": "0x",
            "value": 0,
        }
        return BuiltTx(chain_id=chain_src.chain_id, tx=tx)

    # Convert fee_bps → Across relayerFeePct (18-decimal fixed-point)
    # fee_bps / 10_000 * 10^18  ==  fee_bps * 10^14
    relayer_fee_pct: int = step.bridge_fee_bps * 10**14
    quote_timestamp = int(datetime.now(timezone.utc).timestamp())

    w3 = w3_for(chain_src)
    sender_cs = Web3.to_checksum_address(sender)
    nonce = w3.eth.get_transaction_count(sender_cs) + nonce_offset

    spoke_pool = w3.eth.contract(
        address=Web3.to_checksum_address(spoke_pool_address),
        abi=ACROSS_SPOKE_POOL_ABI,
    )
    tx = spoke_pool.functions.deposit(
        Web3.to_checksum_address(step.recipient),
        Web3.to_checksum_address(step.token),
        step.amount,
        step.dst_chain_id,
        relayer_fee_pct,
        quote_timestamp,
        b"",            # no hook message
        2**256 - 1,     # maxCount: pass max uint256 to skip the per-deposit size cap
    ).build_transaction(
        {
            "chainId": chain_src.chain_id,
            "from": sender_cs,
            "nonce": nonce,
        }
    )
    return BuiltTx(chain_id=chain_src.chain_id, tx=tx)
