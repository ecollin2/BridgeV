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

def force_register_and_wrap():
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

    tokens = [
        "0xc677c31AD31F73A5290f5ef067F8CEF8d301e45c",
        "0x0773b81e0524447784CcE1F3808fed6AaA156eC8"
    ]

    for token in tokens:
        token = Web3.to_checksum_address(token)

        # Register on source
        try:
            if not source.functions.approved(token).call():
                print(f"Registering token {token} on Source...")
                tx = source.functions.registerToken(token).build_transaction({
                    "from": admin_address,
                    "gas": 200000,
                    "gasPrice": avax.eth.gas_price,
                    "nonce": avax.eth.get_transaction_count(admin_address),
                })
                signed = avax.eth.account.sign_transaction(tx, private_key=admin_private_key)
                tx_hash = avax.eth.send_raw_transaction(signed.rawTransaction)
                avax.eth.wait_for_transaction_receipt(tx_hash)
                print(f"✅ Registered: {avax.to_hex(tx_hash)}")
            else:
                print(f"Already registered: {token}")
        except Exception as e:
            print(f"❌ Could not check or register token {token}: {e}")

        # Create token on destination
        try:
            wrapped = destination.functions.wrapped_tokens(token).call()
            if wrapped == "0x0000000000000000000000000000000000000000":
                print(f"Creating wrapped token for {token} on Destination...")
                tx = destination.functions.createToken(token, "Wrapped", "WRP").build_transaction({
                    "from": admin_address,
                    "gas": 300000,
                    "gasPrice": bsc.eth.gas_price,
                    "nonce": bsc.eth.get_transaction_count(admin_address),
                })
                signed = bsc.eth.account.sign_transaction(tx, private_key=admin_private_key)
                tx_hash = bsc.eth.send_raw_transaction(signed.rawTransaction)
                bsc.eth.wait_for_transaction_receipt(tx_hash)
                print(f"✅ Wrapped token created: {bsc.to_hex(tx_hash)}")
            else:
                print(f"Already wrapped: {token}")
        except Exception as e:
            print(f"❌ Failed to wrap token {token}: {e}")

if __name__ == "__main__":
    force_register_and_wrap()
