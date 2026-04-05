from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any


class QuoteRequest(BaseModel):
    # Swap leg A (chain A) -> bridge -> leg B (chain B)
    chain_a_token_in: str
    chain_a_token_out: str  # likely XCN or intermediate
    amount_in: int

    chain_b_token_in: str
    chain_b_token_out: str

    slippage_bps: int = Field(default=50, ge=1, le=2000)  # 0.5% default


class QuoteResponse(BaseModel):
    leg_a_amount_out: int
    leg_b_amount_out: int
    route: Dict[str, Any]


class BuildRequest(BaseModel):
    sender_evm_address: str
    recipient_evm_address: str

    # Same fields as quote
    chain_a_token_in: str
    chain_a_token_out: str
    amount_in: int

    chain_b_token_in: str
    chain_b_token_out: str

    slippage_bps: int = Field(default=50, ge=1, le=2000)

    # What token/amount crosses the bridge:
    bridge_token: str
    bridge_amount: int

    # Path lists can be provided, or we default to [in, out]
    chain_a_path: Optional[List[str]] = None
    chain_b_path: Optional[List[str]] = None


class BuiltTxOut(BaseModel):
    chain_id: int
    tx: Dict[str, Any]
    kind: Literal["approve", "swap", "bridge"]


class BuildResponse(BaseModel):
    unsigned_txs: List[BuiltTxOut]
    notes: List[str]
