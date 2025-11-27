import streamlit as st
from uni_v3_kit.analyzer import MarketScanner
from uni_v3_kit.data_provider import DataProvider

st.set_page_config(page_title="Cazador V3 Pro", layout="wide")

st.title("🦄 Cazador de Oportunidades Uniswap V3 (Pro)")
st.markdown("""
Analiza la rentabilidad real ajustada al riesgo.  
**Fórmula:** `Margen = APR Promedio - (Volatilidad Real² / 2)`
""")

@st.cache_data(ttl=3600)
def get_chains_disponibles():
    provider = DataProvider()
    try:
        pools = provider.get_all_pools()
        chains = {pool.get('ChainId') for pool in pools if pool.get('ChainId')}
        return sorted(list(chains))
    except:
        return ["ethereum", "base", "bsc", "arbitrum"]

# --- SIDEBAR ---
st.sidebar.header("🎯 Configuración de Escaneo")

with st.spinner("Cargando redes..."):
    lista_redes = get_chains_disponibles()

chain = st.sidebar.selectbox("Red (Chain)", lista_redes)
min_tvl = st.sidebar.number_input("Liquidez Mínima ($)", value=50000, step=10000)

st.sidebar.markdown("---")
st.sidebar.header("⏳ Ventana de Análisis")
dias_analisis = st.sidebar.select_slider(
    "Calcular medias sobre:",
    options=[3, 7, 14, 30],
    value=7,
    help="Toma los últimos X días para calcular el APR promedio y la volatilidad."
)

st.sidebar.info(f"Se analizarán aprox. {dias_analisis*3} puntos de datos por pool.")

# --- ESCANER ---
if st.sidebar.button("🔍 Escanear Mercado"):
    scanner = MarketScanner()
    
    with st.spinner(f"Analizando {chain} (Media móvil {dias_analisis} días)..."):
        try:
            df = scanner.scan(chain_filter=chain, min_tvl=min_tvl, days_window=dias_analisis)
            
            if not df.empty:
                st.success(f"¡Análisis completado! Encontrados {len(df)} pools.")
                
                # Configuración visual robusta (Formato estándar)
                # %.1f%% -> Toma el número 50.5, píntalo con 1 decimal (50.5) y añade un % literal.
                column_config = {
                    "Par": st.column_config.TextColumn("Par", width="medium", help="Nombre oficial del pool"),
                    "Red": st.column_config.TextColumn("Red"),
                    "DEX": st.column_config.TextColumn("DEX"),
                    "TVL": st.column_config.NumberColumn(
                        "TVL",
                        format="$%d",
                    ),
                    "APR Media": st.column_config.NumberColumn(
                        "APR Media",
                        format="%.1f%%"
                    ),
                    "Volatilidad": st.column_config.NumberColumn(
                        "Volatilidad",
                        format="%.1f%%" 
                    ),
                    "Riesgo IL": st.column_config.NumberColumn(
                        "Riesgo IL",
                        format="%.1f%%"
                    ),
                    "Margen": st.column_config.NumberColumn(
                        "Margen",
                        format="%.1f%%"
                    ),
                    "Veredicto": st.column_config.TextColumn("Veredicto")
                }
                
                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config=column_config
                )
                
                st.markdown(f"""
                **Detalles del reporte:**
                * **APR Media:** Rendimiento promedio anualizado en los últimos {dias_analisis} días.
                * **Volatilidad:** Fluctuación del precio nativo (Ratio A/B) anualizada.
                """)
            else:
                st.warning(f"No se encontraron pools en {chain} con TVL > ${min_tvl:,.0f}")
                
        except Exception as e:
            st.error(f"Ocurrió un error crítico: {e}")

else:
    st.info("👈 Configura los filtros y pulsa 'Escanear Mercado'.")
