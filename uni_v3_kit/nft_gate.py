from web3 import Web3

# --- CONFIGURACIÓN ---
# RPC Público de Arbitrum One
ARBITRUM_RPC = "https://arb1.arbitrum.io/rpc"

# Dirección del contrato NFT que da acceso (Ejemplo: Arbitrum Odyssey o tu colección)
# CÁMBIALO POR TU CONTRATO
NFT_CONTRACT_ADDRESS = "0xF4820467171695F4d2760614C77503147A9CB1E8" 

# ABI Mínimo para consultar saldo (balanceOf) de un ERC-721
ERC721_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

def check_access(user_address):
    """
    Verifica si una dirección tiene al menos 1 NFT de la colección requerida.
    Retorna: (Bool: Acceso, String: Mensaje)
    """
    if not user_address:
        return False, "Por favor, introduce una dirección."
    
    try:
        # 1. Conectar a Arbitrum
        w3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))
        
        if not w3.is_connected():
            return False, "Error de conexión con la red Arbitrum."
        
        # 2. Validar dirección (Checksum)
        if not w3.is_address(user_address):
            return False, "Dirección de billetera no válida."
        
        checksum_address = w3.to_checksum_address(user_address)
        contract_address = w3.to_checksum_address(NFT_CONTRACT_ADDRESS)
        
        # 3. Instanciar contrato
        contract = w3.eth.contract(address=contract_address, abi=ERC721_ABI)
        
        # 4. Consultar saldo
        balance = contract.functions.balanceOf(checksum_address).call()
        
        if balance > 0:
            return True, f"¡Acceso concedido! Tienes {balance} NFT(s)."
        else:
            return False, "Acceso denegado. No posees el NFT requerido en Arbitrum."
            
    except Exception as e:
        return False, f"Error técnico: {str(e)}"
