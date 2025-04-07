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

    # Define chain and contract info
    chain_name = 'avax' if chain == 'source' else 'bsc'
    w3 = connectTo(chain_name)
    contract_data = getContractInfo(chain)
    contract_address = w3.to_checksum_address(contract_data['address'])
    contract_abi = contract_data['abi']
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)

    latest_block = w3.eth.block_number
    start_block = max(0, latest_block - 4)

    for block in range(start_block, latest_block + 1):
        if chain == 'source':
            events = contract.events.Deposit.create_filter(fromBlock=block, toBlock=block).get_all_entries()
            for event in events:
                token = event.args.token
                recipient = event.args.recipient
                amount = event.args.amount
                print(f"[SOURCE] Deposit: {amount} of {token} for {recipient}")

                # Wrap tokens on destination
                dest_w3 = connectTo("bsc")
                dest_info = getContractInfo("destination")
                dest_contract = dest_w3.eth.contract(address=dest_w3.to_checksum_address(dest_info["address"]), abi=dest_info["abi"])

                tx = dest_contract.functions.wrap(token, recipient, amount).build_transaction({
                    "from": admin_address,
                    "gas": 300000,
                    "gasPrice": dest_w3.eth.gas_price,
                    "nonce": dest_w3.eth.get_transaction_count(admin_address),
                })
                signed = dest_w3.eth.account.sign_transaction(tx, private_key=admin_private_key)
                dest_w3.eth.send_raw_transaction(signed.rawTransaction)
                print("→ wrap() called on destination")

        elif chain == 'destination':
            events = contract.events.Unwrap.create_filter(fromBlock=block, toBlock=block).get_all_entries()
            for event in events:
                underlying = event.args.underlying_token
                recipient = event.args.to
                amount = event.args.amount
                print(f"[DESTINATION] Unwrap: {amount} of {underlying} to {recipient}")

                # Withdraw from source
                src_w3 = connectTo("avax")
                src_info = getContractInfo("source")
                src_contract = src_w3.eth.contract(address=src_w3.to_checksum_address(src_info["address"]), abi=src_info["abi"])

                tx = src_contract.functions.withdraw(underlying, recipient, amount).build_transaction({
                    "from": admin_address,
                    "gas": 300000,
                    "gasPrice": src_w3.eth.gas_price,
                    "nonce": src_w3.eth.get_transaction_count(admin_address),
                })
                signed = src_w3.eth.account.sign_transaction(tx, private_key=admin_private_key)
                src_w3.eth.send_raw_transaction(signed.rawTransaction)
                print("→ withdraw() called on source")

        time.sleep(2)  
