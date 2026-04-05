from dataclasses import dataclass
from typing import Dict, Any
from app.evm.tx_builder import BuiltTx
from app.evm.client import EvmChain


@dataclass
class BridgeStep:
    # A generic representation of what we intend to bridge.
    src_chain_id: int
    dst_chain_id: int
    token: str
    amount: int
    recipient: str


def build_bridge_tx(chain_src: EvmChain, sender: str, step: BridgeStep) -> BuiltTx:
    """
    Stub: This must be implemented for a real bridge provider.
    Options include Across, Stargate, Hop, etc.

    This returns an unsigned tx dict that the frontend wallet can sign.
    """
    # Placeholder tx that cannot be executed:
    tx: Dict[str, Any] = {
        "chainId": chain_src.chain_id,
        "from": sender,
        "to": "0x0000000000000000000000000000000000000000",
        "nonce": 0,
        "data": "0x",
        "value": 0,
    }
    return BuiltTx(chain_id=chain_src.chain_id, tx=tx)
    
