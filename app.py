import streamlit as st
from nft_gate import check_nft_ownership

st.title("🔒 Acceso para Holders de NFT")

wallet_address = st.text_input("Introduce tu dirección de billetera:")

if st.button("Verificar"):  
    with st.spinner("Verificando..."):
        if check_nft_ownership(wallet_address):
            st.success("Acceso concedido. ¡Bienvenido, holder!")
            # Aquí puedes mostrar tu contenido exclusivo
        else:
            st.error("Acceso denegado. No se encontró el NFT en esta billetera.")
