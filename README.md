# Agro-Onyx_Backend
BackEnd for new Aggregator/Swap


# Agro-Onyx_Backend
BackEnd for new Aggregator/Swap

How to use:
pip install -r requirements.txt
bash run.sh


register and login:
curl -s http://localhost:8000/auth/register -H "content-type: application/json" \
  -d '{"username":"u1","password":"p1"}'

TOKEN=$(curl -s http://localhost:8000/auth/login -H "content-type: application/json" \
  -d '{"username":"u1","password":"p1"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo $TOKEN


v1 Bash quote:

curl -s http://localhost:8000/v1/quote \
  -H "authorization: Bearer $TOKEN" -H "content-type: application/json" \
  -d '{
    "chain_a_token_in":"0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "chain_a_token_out":"0xa2cd3d43c775978a96bdbf12d733d5a1ed94fb18",
    "amount_in": 1000000,
    "chain_b_token_in":"0xa2cd3d43c775978a96bdbf12d733d5a1ed94fb18",
    "chain_b_token_out":"0x82af49447d8a07e3bd95bd0d56f35241523fbab1",
    "slippage_bps": 50
  }' | jq


  Next decisions for build:
  Which bridge provider do you want for chain A ↔ chain B?
Across / Stargate / Hop / LayerZero / Wormhole (EVM) etc.
Once you pick one, replace the stub with real aggregator.
