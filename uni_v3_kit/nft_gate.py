from web3 import Web3
from eth_account.messages import encode_defunct

# --- CONFIGURACIÓN ---
ARBITRUM_RPC = "https://arb1.arbitrum.io/rpc"
# Contrato NFT (Ejemplo: Arbitrum Odyssey) - CÁMBIALO POR EL TUYO
NFT_CONTRACT_ADDRESS = "0xF4820467171695F4d2760614C77503147A9CB1E8" 

ERC721_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

def verify_signature(address, signature, message_text="Acceso a Cazador V3"):
    """
    Recupera la dirección que firmó el mensaje y comprueba si coincide.
    """
    try:
        w3 = Web3()
        # Codificar el mensaje según el estándar EIP-191
        message_encoded = encode_defunct(text=message_text)
        
        # Recuperar la dirección pública del firmante
        signer = w3.eth.account.recover_message(message_encoded, signature=signature)
        
        return signer.lower() == address.lower()
    except Exception as e:
        print(f"Error firma: {e}")
        return False

def check_access(user_address):
    """
    Verifica saldo NFT en Arbitrum.
    """
    if not user_address: return False, "Dirección vacía"
    
    try:
        w3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))
        if not w3.is_connected(): return False, "Error conexión RPC"
        
        checksum_addr = w3.to_checksum_address(user_address)
        contract_addr = w3.to_checksum_address(NFT_CONTRACT_ADDRESS)
        contract = w3.eth.contract(address=contract_addr, abi=ERC721_ABI)
        
        balance = contract.functions.balanceOf(checksum_addr).call()
        
        if balance > 0:
            return True, f"¡Holder verificado! Tienes {balance} NFT(s)."
        return False, "No tienes el NFT requerido."
    except Exception as e:
        return False, f"Error verificando NFT: {str(e)}"
