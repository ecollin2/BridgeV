from web3 import Web3
from web3.contract import Contract
from web3.providers.rpc import HTTPProvider
from web3.middleware import geth_poa_middleware
import json
import sys
from pathlib import Path
import time


contract_info = "contract_info.json"

admin_address = "0x4d9BD0fa70042aB46721cDD0B00Ed64093A48ea0"
admin_private_key = "d43a2a59e59104117f0c705ff5bd2936f7d77bb4d5f62a9bef0957aa0fc47cea"

def connectTo(chain):
    if chain == 'avax':
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc"
    elif chain == 'bsc':
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/"
    else:
        print(f"{chain} is not a valid chain")
        return None

    w3 = Web3(Web3.HTTPProvider(api_url))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3

def getContractInfo(chain):
    try:
        with open(contract_info, 'r') as f:
            contracts = json.load(f)
    except Exception as e:
        print("Failed to read contract info")
        print(e)
        sys.exit(1)

    return contracts[chain]

def scanBlocks(chain):
    if chain not in ['source', 'destination']:
        print(f"Invalid chain: {chain}")
        return

    chain_name = 'avax' if chain == 'source' else 'bsc'
    w3 = connectTo(chain_name)
    contract_data = getContractInfo(chain)
    contract_address = w3.to_checksum_address(contract_data['address'])
    contract_abi = contract_data['abi']
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)

    latest_block = w3.eth.block_number
    start_block = max(0, latest_block - 4)

    if chain == 'source':
        dest_w3 = connectTo("bsc")
        dest_info = getContractInfo("destination")
        dest_contract = dest_w3.eth.contract(address=dest_w3.to_checksum_address(dest_info["address"]), abi=dest_info["abi"])
        nonce = dest_w3.eth.get_transaction_count(admin_address)

        for block in range(start_block, latest_block + 1):
            events = contract.events.Deposit.create_filter(fromBlock=block, toBlock=block).get_all_entries()
            for event in events:
                tx_hash = event.transactionHash.hex()
                if tx_hash in processed_txs:
                    continue
                processed_txs.add(tx_hash)

                token = event.args.token
                recipient = event.args.recipient
                amount = event.args.amount
                print(f"[SOURCE] Deposit: {amount} of {token} for {recipient}")

                tx = dest_contract.functions.wrap(token, recipient, amount).build_transaction({
                    "from": admin_address,
                    "gas": 300000,
                    "gasPrice": dest_w3.eth.gas_price,
                    "nonce": nonce,
                })
                signed = dest_w3.eth.account.sign_transaction(tx, private_key=admin_private_key)
                tx_hash = dest_w3.eth.send_raw_transaction(signed.rawTransaction)
                print(f"→ wrap() sent: {dest_w3.to_hex(tx_hash)}")
                nonce += 1

    elif chain == 'destination':
        src_w3 = connectTo("avax")
        src_info = getContractInfo("source")
        src_contract = src_w3.eth.contract(address=src_w3.to_checksum_address(src_info["address"]), abi=src_info["abi"])
        nonce = src_w3.eth.get_transaction_count(admin_address)

        for block in range(start_block, latest_block + 1):
            events = contract.events.Unwrap.create_filter(fromBlock=block, toBlock=block).get_all_entries()
            for event in events:
                tx_hash = event.transactionHash.hex()
                if tx_hash in processed_txs:
                    continue
                processed_txs.add(tx_hash)

                underlying = event.args.underlying_token
                recipient = event.args.to
                amount = event.args.amount
                print(f"[DESTINATION] Unwrap: {amount} of {underlying} to {recipient}")

                tx = src_contract.functions.withdraw(underlying, recipient, amount).build_transaction({
                    "from": admin_address,
                    "gas": 300000,
                    "gasPrice": src_w3.eth.gas_price,
                    "nonce": nonce,
                })
                signed = src_w3.eth.account.sign_transaction(tx, private_key=admin_private_key)
                tx_hash = src_w3.eth.send_raw_transaction(signed.rawTransaction)
                print(f"→ withdraw() sent: {src_w3.to_hex(tx_hash)}")
                nonce += 1

    time.sleep(2)

if __name__ == "__main__":
    scanBlocks("source")
    scanBlocks("destination")
