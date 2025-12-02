import streamlit as st
import streamlit.components.v1 as components
from privy import PrivyAPI
from moralis import evm_api
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="App Segura con Privy",
    page_icon="🔐",
    layout="centered"
)

# --- CONFIGURACIÓN DEL TOKEN GATING ---
# ¡IMPORTANTE! Reemplaza este valor con la dirección de tu contrato de NFT.
NFT_CONTRACT_ADDRESS = "0xF4820467171695F4d2760614C77503147A9CB1E8" # <-- CAMBIA ESTO
CHAIN = "arbitrum"

# --- CARGAR SECRETOS DE FORMA SEGURA ---
try:
    PRIVY_APP_ID = st.secrets["PRIVY_APP_ID"]
    PRIVY_APP_SECRET = st.secrets["PRIVY_APP_SECRET"]
    MORALIS_API_KEY = st.secrets["MORALIS_API_KEY"]
except KeyError as e:
    st.error(f"Error: El secreto {e.args[0]} no fue encontrado. Por favor, configúralo en Streamlit Cloud.")
    st.stop()

# --- INICIALIZAR CLIENTES DE API ---
privy_client = PrivyAPI(PRIVY_APP_ID, PRIVY_APP_SECRET)

# --- INTERFAZ DE USUARIO ---
st.title("💎 Verificación de Holder con Firma Segura 💎")
st.write("Para acceder al contenido exclusivo, debes verificar que eres el dueño de un NFT específico conectando tu billetera.")
st.write("--- ")

# --- LÓGICA PRINCIPAL ---
# Usamos st.session_state para guardar el estado de la autenticación
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Si el usuario ya está autenticado y verificado, muestra el contenido
if st.session_state.authenticated:
    st.success("¡Autenticación y verificación completadas! Bienvenido. 🎉")
    st.balloons()
    
    # --- CONTENIDO EXCLUSIVO ---
    st.header("Área Secreta para Holders")
    st.write("Este es el contenido exclusivo que has desbloqueado.")
    st.image("https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2t2eGJkZ2dveWJtN2VqdGg2eXNpcjZqZzZqenBma3JzNnBqY2VpZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/NEvPzZ8bd1V4Y/giphy.gif", caption="¡Acceso concedido!" )

else:
    # Si no está autenticado, muestra el componente de login
    st.subheader("Paso 1: Conecta tu Billetera")
    st.caption("Al hacer clic, se abrirá la interfaz de Privy para que conectes tu billetera de forma segura.")

    # Cargar el componente HTML
    try:
        with open(os.path.join('components', 'privy_component.html'), 'r') as f:
            html_content = f.read()
        
        # Reemplazar el placeholder con el App ID real
        html_content = html_content.replace('{{PRIVY_APP_ID}}', PRIVY_APP_ID)
        
        # Renderizar el componente y esperar una respuesta
        component_value = components.html(html_content, height=60)

        if component_value:
            if 'error' in component_value:
                st.error(f"Error de autenticación: {component_value['error']}")
            elif 'token' in component_value:
                access_token = component_value['token']
                
                with st.spinner("Verificando token y buscando tu NFT..."):
                    try:
                        # Paso 1: Verificar el token con Privy
                        auth_info = privy_client.verify_auth_token(access_token)
                        user_wallet = auth_info.user_id
                        st.info(f"Token verificado. Dirección de billetera: {user_wallet}")

                        # Paso 2: Verificar la posesión del NFT con Moralis
                        result = evm_api.nft.get_wallet_nfts(
                            api_key=MORALIS_API_KEY,
                            params={
                                "address": user_wallet,
                                "chain": CHAIN,
                                "token_addresses": [NFT_CONTRACT_ADDRESS]
                            }
                        )

                        if result.get("result") and len(result["result"]) > 0:
                            # Si todo es correcto, marca al usuario como autenticado y recarga la página
                            st.session_state.authenticated = True
                            st.experimental_rerun()
                        else:
                            st.warning("Acceso Denegado. La billetera conectada no posee el NFT requerido.")

                    except Exception as e:
                        st.error(f"Ocurrió un error durante la verificación: {e}")

    except FileNotFoundError:
        st.error("Error: No se encontró el archivo 'components/privy_component.html'. Asegúrate de que la carpeta y el archivo existen en tu repositorio.")
