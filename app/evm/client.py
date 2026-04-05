from dataclasses import dataclass
from web3 import Web3


@dataclass
class EvmChain:
    chain_id: int
    rpc_url: str
    router: str


def w3_for(chain: EvmChain) -> Web3:
    w3 = Web3(Web3.HTTPProvider(chain.rpc_url, request_kwargs={"timeout": 30}))
    return w3
