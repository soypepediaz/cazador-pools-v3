from web3 import Web3
import os
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("https://arb-mainnet.g.alchemy.com/v2/AaA4MmE-tGVbo3GTa8o9R")
NFT_CONTRACT_ADDRESS = "0xF4820467171695F4d2760614C77503147A9CB1E8"  # dirección del contrato NFT
ERC721_ABI = [{
    "constant": True,
    "inputs": [{"name": "_owner", "type": "address"}],
    "name": "balanceOf",
    "outputs": [{"name": "balance", "type": "uint256"}],
    "type": "function",
}]

w3 = Web3(Web3.HTTPProvider(RPC_URL))

def check_nft_ownership(wallet_address):
    if not wallet_address:
        return False
    try:
        checksum_address = Web3.to_checksum_address(wallet_address)
        contract = w3.eth.contract(address=NFT_CONTRACT_ADDRESS, abi=ERC721_ABI)
        balance = contract.functions.balanceOf(checksum_address).call()
        return balance > 0
    except Exception as e:
        return False
