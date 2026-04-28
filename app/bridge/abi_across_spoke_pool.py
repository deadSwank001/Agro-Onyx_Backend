# Across Protocol v2 SpokePool ABI (deposit function only).
# Source: https://github.com/across-protocol/contracts-v2
ACROSS_SPOKE_POOL_ABI = [
    {
        "name": "deposit",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {"name": "recipient", "type": "address"},
            {"name": "originToken", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "destinationChainId", "type": "uint256"},
            # 18-decimal fixed-point fee fraction; e.g. 1e15 == 0.1 % fee
            {"name": "relayerFeePct", "type": "int64"},
            {"name": "quoteTimestamp", "type": "uint32"},
            {"name": "message", "type": "bytes"},
            # Pass type(uint256).max to skip the max-deposit size check
            {"name": "maxCount", "type": "uint256"},
        ],
        "outputs": [],
    },
]
