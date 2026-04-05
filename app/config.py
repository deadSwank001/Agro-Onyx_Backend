from pydantic import BaseModel
import os


class Settings(BaseModel):
    # Auth
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-change-me")
    jwt_algorithm: str = os.getenv("JWT_ALG", "HS256")
    jwt_exp_minutes: int = int(os.getenv("JWT_EXP_MINUTES", "120"))

    # EVM RPCs (example names; set in env)
    rpc_chain_a: str = os.getenv("RPC_CHAIN_A", "https://mainnet.infura.io/v3/YOUR_KEY")
    rpc_chain_b: str = os.getenv("RPC_CHAIN_B", "https://arb1.arbitrum.io/rpc")

    # Chain IDs (example; set correctly for your deployment)
    chain_a_id: int = int(os.getenv("CHAIN_A_ID", "1"))       # Ethereum mainnet
    chain_b_id: int = int(os.getenv("CHAIN_B_ID", "42161"))   # Arbitrum

    # UniswapV2-style router addresses (examples; replace as needed)
    # If you need Uniswap V3, the transaction building differs.
    router_chain_a: str = os.getenv("ROUTER_CHAIN_A", "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")  # Uniswap V2 router (mainnet)
    router_chain_b: str = os.getenv("ROUTER_CHAIN_B", "0x0000000000000000000000000000000000000000")  # set this

    # Tokens
    xcn_token: str = os.getenv("XCN_TOKEN", "0xa2cd3d43c775978a96bdbf12d733d5a1ed94fb18")

    # For building transactions we need a deadline horizon (seconds)
    swap_deadline_seconds: int = int(os.getenv("SWAP_DEADLINE_SECONDS", "1200"))  # 20 min


settings = Settings()
