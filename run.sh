#!/usr/bin/env bash
export JWT_SECRET="dev-change-me"
export RPC_CHAIN_A="https://mainnet.infura.io/v3/YOUR_KEY"
export RPC_CHAIN_B="https://arb1.arbitrum.io/rpc"
export CHAIN_A_ID="1"
export CHAIN_B_ID="42161"
export ROUTER_CHAIN_A="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
export ROUTER_CHAIN_B="0x0000000000000000000000000000000000000000"  # set real router
export XCN_TOKEN="0xa2cd3d43c775978a96bdbf12d733d5a1ed94fb18"

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
