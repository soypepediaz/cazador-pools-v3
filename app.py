import streamlit as st
from uni_v3_kit.analyzer import MarketScanner

st.set_page_config(page_title="Cazador V3", layout="wide")

st.title("🦄 Cazador de Oportunidades Uniswap V3")
st.markdown("Analiza volatilidad real vs APR reportado para detectar trampas.")

# --- BARRA LATERAL (FILTROS) ---
st.sidebar.header("Filtros")
chain = st.sidebar.selectbox("Red (Chain)", ["ethereum", "base", "bsc", "arbitrum", "polygon"])
min_tvl = st.sidebar.number_input("Liquidez Mínima ($)", value=50000, step=10000)

if st.sidebar.button("🔍 Escanear Mercado"):
    scanner = MarketScanner()
    
    with st.spinner(f"Descargando datos de {chain} y calculando volatilidades históricas..."):
        try:
            df = scanner.scan(chain_filter=chain, min_tvl=min_tvl)
            
            if not df.empty:
                st.success(f"¡Análisis completado! Encontrados {len(df)} pools.")
                
                # Colorear la tabla según el veredicto
                st.dataframe(df, use_container_width=True)
                
                st.markdown("""
                **Leyenda:**
                * 💎 **GEM:** El APR supera por mucho (>20%) el riesgo de volatilidad.
                * ✅ **OK:** Rentable, pero vigila.
                * ❌ **REKT:** La volatilidad es tan alta que te comerá las ganancias (IL).
                """)
            else:
                st.warning("No se encontraron pools con esos criterios o la API falló.")
                
        except Exception as e:
            st.error(f"Ocurrió un error: {e}")

else:
    st.info("👈 Selecciona los filtros y pulsa 'Escanear Mercado' para empezar.")
