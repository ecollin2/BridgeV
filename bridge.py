def scan_blocks(chain, contract_info="contract_info.json"):
    if chain not in ['source', 'destination']:
        print(f"Invalid chain: {chain}")
        return 0

    w3 = connect_to(chain)
    contracts = get_contract_info(chain, contract_info)
    contract_address = Web3.to_checksum_address(contracts['address'])
    private_key = contracts['signing_key']
    abi = contracts['abi']

    contract = w3.eth.contract(address=contract_address, abi=abi)

    latest = w3.eth.block_number
    start_block = latest - 5
    end_block = latest

    print(f"Scanning {chain} from block {start_block} to {end_block}...")

    if chain == 'source':
        event_obj = contract.events.Deposit
        counterpart = 'destination'
    else:
        event_obj = contract.events.Unwrap
        counterpart = 'source'

    # Get the counterpart Web3 instance and contract
    w3_other = connect_to(counterpart)
    other_contracts = get_contract_info(counterpart, contract_info)
    other_address = Web3.to_checksum_address(other_contracts['address'])
    other_abi = other_contracts['abi']
    other_contract = w3_other.eth.contract(address=other_address, abi=other_abi)

    # Event filtering
    event_filter = event_obj.create_filter(fromBlock=start_block, toBlock=end_block)
    events = event_filter.get_all_entries()

    for evt in events:
        args = evt['args']
        recipient = args['recipient'] if 'recipient' in args else args['to']
        token = args['token']
        amount = args['amount']

        nonce = w3_other.eth.get_transaction_count(Web3.to_checksum_address(w3.eth.account.from_key(private_key).address))
        txn = None

        if chain == 'source':
            # Call wrap on destination chain
            txn = other_contract.functions.wrap(token, recipient, amount).build_transaction({
                'chainId': w3_other.eth.chain_id,
                'gas': 500000,
                'gasPrice': w3_other.eth.gas_price,
                'nonce': nonce
            })
        else:
            txn = other_contract.functions.withdraw(token, recipient, amount).build_transaction({
                'chainId': w3_other.eth.chain_id,
                'gas': 500000,
                'gasPrice': w3_other.eth.gas_price,
                'nonce': nonce
            })

        signed_txn = w3_other.eth.account.sign_transaction(txn, private_key=private_key)
        tx_hash = w3_other.eth.send_raw_transaction(signed_txn.rawTransaction)
        print(f"Sent transaction on {counterpart} for event on {chain}, tx hash: {tx_hash.hex()}")
