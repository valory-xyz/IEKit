from web3 import Web3
import json
from pathlib import Path
import dotenv
import os

dotenv.load_dotenv(".env")

RPC = os.getenv("BASE_LEDGER_RPC")
web3 = Web3(Web3.HTTPProvider(RPC))

def main():
    """Main"""

    # Load
    with open(Path("keys.json"), "r", encoding="utf-8") as keys_file:
        keys = json.load(keys_file)
        wallet_address = keys[0]["address"]
        private_key = keys[0]["private_key"]

        native_balance = web3.eth.get_balance(wallet_address) / 1e18
        print(f"Wallet has {native_balance} ETH")


    def load_contract(contract_name, contract_address):
        """Load a contract"""

        with open(Path("scripts", f"{contract_name}.json"), "r", encoding="utf-8") as abi_file:
            abi = json.load(abi_file)

        return web3.eth.contract(
            address=web3.to_checksum_address(contract_address),
            abi=abi
        )

    # Load contracts
    olas_contract = load_contract("Olas", "0x54330d28ca3357F294334BDC454a032e7f353416")
    contribute_manager_contract = load_contract("ContributeManager", "0xaea9ef993d8a1A164397642648DF43F053d43D85")
    staking_contract_address = "0x95146Adf659f455f300D7521B3b62A3b6c4aBA1F"


    # Approve OLAS
    transaction = olas_contract.functions.approve(
        contribute_manager_contract.address,
        web3.to_wei(10000, "ether")  # approved amount
    ).build_transaction(
        {
            "from": wallet_address,
            "nonce": web3.eth.get_transaction_count(web3.to_checksum_address(wallet_address)),
            "gas": 10000000,
            "gasPrice": web3.to_wei(100, "gwei"),
        }
    )
    signed_tx = web3.eth.account.sign_transaction(transaction, private_key)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    if tx_receipt.status != 1:
        raise ValueError("Approval transaction failed")

    # Stake
    transaction = contribute_manager_contract.functions.createAndStake(
        1761132611533934592,  # tsunami twitter id
        web3.to_checksum_address(staking_contract_address)
    ).build_transaction(
        {
            "from": wallet_address,
            "nonce": web3.eth.get_transaction_count(web3.to_checksum_address(wallet_address)),
            "gas": 10000000,
            "gasPrice": web3.to_wei(100, "gwei"),
            "value": web3.to_wei(2, "wei")  # required for staking
        }
    )
    signed_tx = web3.eth.account.sign_transaction(transaction, private_key)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    if tx_receipt.status != 1:
        raise ValueError("Stake transaction failed")


if __name__ == "__main__":
    main()