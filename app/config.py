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

    # Uniswap V2 factory addresses (used for price-impact computation via getReserves)
    factory_chain_a: str = os.getenv("FACTORY_CHAIN_A", "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f")  # Uniswap V2 factory (mainnet)
    factory_chain_b: str = os.getenv("FACTORY_CHAIN_B", "0x0000000000000000000000000000000000000000")  # set this

    # Tokens
    xcn_token: str = os.getenv("XCN_TOKEN", "0xa2cd3d43c775978a96bdbf12d733d5a1ed94fb18")

    # For building transactions we need a deadline horizon (seconds)
    swap_deadline_seconds: int = int(os.getenv("SWAP_DEADLINE_SECONDS", "1200"))  # 20 min

    # ── Risk controls ────────────────────────────────────────────────────────
    # Maximum input amount in the smallest token unit (default: 10 × 10^18,
    # i.e. 10 ETH-equivalent).  Set MAX_AMOUNT_IN env var to override.
    max_amount_in: int = int(os.getenv("MAX_AMOUNT_IN", str(10 * 10**18)))

    # Maximum slippage tolerance a caller may request (basis points).
    # Default 300 bps = 3 %.  Override with MAX_SLIPPAGE_BPS env var.
    max_slippage_bps: int = int(os.getenv("MAX_SLIPPAGE_BPS", "300"))

    # Maximum combined price impact before a build is refused (basis points).
    # Default 500 bps = 5 %.  Override with MAX_PRICE_IMPACT_BPS env var.
    max_price_impact_bps: int = int(os.getenv("MAX_PRICE_IMPACT_BPS", "500"))

    # Bridge provider fee in basis points deducted from the bridged amount.
    # Set to the actual fee of your bridge provider; 0 means no fee deduction.
    bridge_fee_bps: int = int(os.getenv("BRIDGE_FEE_BPS", "0"))

    # Across Protocol SpokePool address on the source chain.
    # Default is the Across v2 SpokePool on Ethereum mainnet (chain ID 1).
    # Override with SPOKE_POOL_CHAIN_A env var for other networks.
    spoke_pool_chain_a: str = os.getenv(
        "SPOKE_POOL_CHAIN_A", "0x5c7BCd6E7De5423a257D81B442095A1a6ced35C5"
    )


settings = Settings()
