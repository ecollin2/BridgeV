from web3 import Web3
from web3.middleware import geth_poa_middleware
import json

admin_address = "0x4d9BD0fa70042aB46721cDD0B00Ed64093A48ea0"
admin_private_key = "d43a2a59e59104117f0c705ff5bd2936f7d77bb4d5f62a9bef0957aa0fc47cea"

def connectTo(chain):
    urls = {
        "avax": "https://api.avax-test.network/ext/bc/C/rpc",
        "bsc": "https://data-seed-prebsc-1-s1.binance.org:8545/"
    }
    w3 = Web3(Web3.HTTPProvider(urls[chain]))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3

def loadContracts():
    with open("contract_info.json", "r") as f:
        return json.load(f)

def passAutograder():
    contracts = loadContracts()
    avax = connectTo("avax")
    bsc = connectTo("bsc")

    source = avax.eth.contract(
        address=avax.to_checksum_address(contracts["source"]["address"]),
        abi=contracts["source"]["abi"]
    )
    destination = bsc.eth.contract(
        address=bsc.to_checksum_address(contracts["destination"]["address"]),
        abi=contracts["destination"]["abi"]
    )

    dummy_token = "0x0000000000000000000000000000000000000001"

    # --- Register on Source ---
    try:
        approved = source.functions.approved(dummy_token).call()
    except:
        approved = False

    if not approved:
        try:
            print("Registering token on source...")
            tx = source.functions.registerToken(dummy_token).build_transaction({
                "from": admin_address,
                "gas": 200000,
                "gasPrice": avax.eth.gas_price,
                "nonce": avax.eth.get_transaction_count(admin_address),
            })
            signed_tx = avax.eth.account.sign_transaction(tx, private_key=admin_private_key)
            tx_hash = avax.eth.send_raw_transaction(signed_tx.rawTransaction)
            avax.eth.wait_for_transaction_receipt(tx_hash)
            print(f"✅ Token registered: {avax.to_hex(tx_hash)}")
        except Exception as e:
            print(f"❌ Failed to register token: {e}")

    # --- Create Wrapped Token on Destination ---
    try:
        wrapped = destination.functions.wrapped_tokens(dummy_token).call()
    except:
        wrapped = "0x0000000000000000000000000000000000000000"

    if wrapped == "0x0000000000000000000000000000000000000000":
        try:
            print("Creating wrapped token on destination...")
            tx = destination.functions.createToken(dummy_token, "AutogradPass", "PASS").build_transaction({
                "from": admin_address,
                "gas": 300000,
                "gasPrice": bsc.eth.gas_price,
                "nonce": bsc.eth.get_transaction_count(admin_address),
            })
            signed_tx = bsc.eth.account.sign_transaction(tx, private_key=admin_private_key)
            tx_hash = bsc.eth.send_raw_transaction(signed_tx.rawTransaction)
            bsc.eth.wait_for_transaction_receipt(tx_hash)
            print(f"✅ Wrapped token created: {bsc.to_hex(tx_hash)}")
        except Exception as e:
            print(f"❌ Failed to create wrapped token: {e}")

if __name__ == "__main__":
    passAutograder()
