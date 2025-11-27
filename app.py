import streamlit as st
from uni_v3_kit.analyzer import MarketScanner
from uni_v3_kit.data_provider import DataProvider

st.set_page_config(page_title="Cazador V3", layout="wide")

st.title("🦄 Cazador de Oportunidades Uniswap V3")
st.markdown("Analiza volatilidad real vs APR reportado para detectar trampas.")

# --- FUNCIÓN PARA OBTENER REDES AUTOMÁTICAMENTE ---
@st.cache_data(ttl=3600) # Guardar en memoria 1 hora para no saturar la API
def get_chains_disponibles():
    provider = DataProvider()
    try:
        pools = provider.get_all_pools()
        # Creamos un conjunto (set) para tener solo valores únicos y eliminamos nulos
        chains = {pool.get('ChainId') for pool in pools if pool.get('ChainId')}
        return sorted(list(chains)) # Devolvemos lista ordenada alfabéticamente
    except:
        return ["ethereum"] # Fallback por si falla la API

# --- BARRA LATERAL (FILTROS) ---
st.sidebar.header("Filtros")

# 1. Cargamos las redes dinámicamente
with st.spinner("Cargando redes disponibles..."):
    lista_redes = get_chains_disponibles()

if not lista_redes:
    st.error("No se pudieron cargar las redes de la API.")
    lista_redes = ["ethereum", "base", "bsc", "arbitrum"] # Lista de emergencia

# 2. El selector ahora usa la lista dinámica
chain = st.sidebar.selectbox("Red (Chain)", lista_redes)

min_tvl = st.sidebar.number_input("Liquidez Mínima ($)", value=50000, step=10000)

# --- BOTÓN DE ESCANEO ---
if st.sidebar.button("🔍 Escanear Mercado"):
    scanner = MarketScanner()
    
    with st.spinner(f"Analizando pools en {chain} y calculando volatilidades históricas..."):
        try:
            # Llamamos al scanner pasando la red seleccionada
            df = scanner.scan(chain_filter=chain, min_tvl=min_tvl)
            
            if not df.empty:
                st.success(f"¡Análisis completado! Encontrados {len(df)} pools en {chain}.")
                
                # Mostramos la tabla
                st.dataframe(df, use_container_width=True)
                
                st.markdown("""
                **Leyenda:**
                * 💎 **GEM:** El APR supera por mucho (>20%) el riesgo de volatilidad.
                * ✅ **OK:** Rentable (Margen > 5%).
                * ⚠️ **JUSTO:** El APR apenas cubre el riesgo.
                * ❌ **REKT:** La volatilidad histórica es mayor que el APR. Perderás dinero.
                """)
            else:
                st.warning(f"No se encontraron pools en {chain} con TVL > ${min_tvl:,.0f}")
                
        except Exception as e:
            st.error(f"Ocurrió un error durante el análisis: {e}")

else:
    st.info(f"👈 Hay {len(lista_redes)} redes disponibles. Selecciona una y pulsa 'Escanear'.")
