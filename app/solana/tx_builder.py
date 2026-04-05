from dataclasses import dataclass
from typing import Any, Dict

# NOTE: Included for future Solana route legs. Not used in the EVM-only route below.
from solana.rpc.api import Client
from solders.pubkey import Pubkey


@dataclass
class SolanaUnsignedTx:
    # Placeholder type: in real usage you'd return a base64-encoded transaction message
    # for wallet signing (or a serialized VersionedTransaction).
    message: str
    meta: Dict[str, Any]


def get_spl_balance(rpc_url: str, owner: str, mint: str) -> int:
    """
    Basic helper to demonstrate SolanaPy presence.
    For actual SPL balance you typically query token accounts by owner + mint.
    """
    client = Client(rpc_url)
    _owner = Pubkey.from_string(owner)
    _mint = Pubkey.from_string(mint)
    # Not implemented fully; requires token program parsing.
    raise NotImplementedError("Wire SPL token account lookup for owner+mint when needed.")
