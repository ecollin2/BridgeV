admin_address = "0x4d9BD0fa70042aB46721cDD0B00Ed64093A48ea0"
admin_private_key = "d43a2a59e59104117f0c705ff5bd2936f7d77bb4d5f62a9bef0957aa0fc47cea"

def connectTo(chain):
    urls = {
        "avax": "https://api.avax-test.network/ext/bc/C/rpc",
        "bsc": "https://data-seed-prebsc-1-s1.binance.org:8545/",
    }
    w3 = Web3(Web3.HTTPProvider(urls[chain]))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3

def loadContracts():
    with open("contract_info.json", "r") as f:
        return json.load(f)

def bridgeListener():
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

    nonce = bsc.eth.get_transaction_count(admin_address)
    processed_txs = set()
    latest_block = avax.eth.block_number
    start_block = max(0, latest_block - 5)

    for block in range(start_block, latest_block + 1):
        try:
            events = source.events.Deposit.create_filter(fromBlock=block, toBlock=block).get_all_entries()
        except Exception as e:
            print(f"Error fetching events: {e}")
            continue

        for event in events:
            tx_hash = event.transactionHash.hex()
            if tx_hash in processed_txs:
                continue
            processed_txs.add(tx_hash)

            token = event.args.token
            recipient = event.args.recipient
            amount = event.args.amount
            print(f"[SOURCE] Deposit: {amount} of {token} for {recipient}")

            try:
                wrapped_token = destination.functions.wrapped_tokens(token).call()
            except Exception as e:
                print(f"Error calling wrapped_tokens: {e}")
                continue

            if wrapped_token == "0x0000000000000000000000000000000000000000":
                print(f"Token {token} not wrapped yet — calling createToken()")
                try:
                    tx = destination.functions.createToken(
                        token,
                        "Test Wrapped Token",
                        "TWT"
                    ).build_transaction({
                        "from": admin_address,
                        "gas": 300000,
                        "gasPrice": bsc.eth.gas_price,
                        "nonce": nonce,
                    })
                    signed = bsc.eth.account.sign_transaction(tx, private_key=admin_private_key)
                    tx_hash = bsc.eth.send_raw_transaction(signed.rawTransaction)
                    bsc.eth.wait_for_transaction_receipt(tx_hash)
                    print(f"→ Token created: {bsc.to_hex(tx_hash)}")
                    nonce += 1
                except Exception as e:
                    print(f"Error creating token: {e}")
                    continue

            try:
                tx = destination.functions.wrap(token, recipient, amount).build_transaction({
                    "from": admin_address,
                    "gas": 300000,
                    "gasPrice": bsc.eth.gas_price,
                    "nonce": nonce,
                })
                signed = bsc.eth.account.sign_transaction(tx, private_key=admin_private_key)
                tx_hash = bsc.eth.send_raw_transaction(signed.rawTransaction)
                print(f"→ wrap() sent: {bsc.to_hex(tx_hash)}")
                nonce += 1
            except Exception as e:
                print(f"Error sending wrap transaction: {e}")
                continue

    print("Bridge listener run complete.")

if __name__ == "__main__":
    bridgeListener()
