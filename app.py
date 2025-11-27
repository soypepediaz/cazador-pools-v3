import streamlit as st
from uni_v3_kit.analyzer import MarketScanner
from uni_v3_kit.data_provider import DataProvider

st.set_page_config(page_title="Cazador V3 Pro", layout="wide")

st.title("🦄 Cazador de Oportunidades Uniswap V3 (Pro)")
st.markdown("""
Analiza la rentabilidad real ajustada al riesgo.  
**Fórmula:** `Margen = APR Promedio - (Volatilidad Real² / 2)`
""")

# --- CACHE DE REDES ---
@st.cache_data(ttl=3600)
def get_chains_disponibles():
    provider = DataProvider()
    try:
        pools = provider.get_all_pools()
        chains = {pool.get('ChainId') for pool in pools if pool.get('ChainId')}
        return sorted(list(chains))
    except:
        return ["ethereum", "base", "bsc", "arbitrum"]

# --- BARRA LATERAL ---
st.sidebar.header("🎯 Configuración de Escaneo")

with st.spinner("Cargando redes..."):
    lista_redes = get_chains_disponibles()

# 1. Filtros Básicos
chain = st.sidebar.selectbox("Red (Chain)", lista_redes)
min_tvl = st.sidebar.number_input("Liquidez Mínima ($)", value=50000, step=10000)

st.sidebar.markdown("---")

# 2. Configuración de Ventana de Tiempo (NUEVO)
st.sidebar.header("⏳ Ventana de Análisis")
dias_analisis = st.sidebar.select_slider(
    "Calcular medias sobre:",
    options=[3, 7, 14, 30],
    value=7,
    help="Toma los últimos X días para calcular el APR promedio y la volatilidad. Evita picos falsos de un solo día."
)

st.sidebar.info(f"Se analizarán aprox. {dias_analisis*3} puntos de datos por pool.")

# --- BOTÓN DE ACCIÓN ---
if st.sidebar.button("🔍 Escanear Mercado"):
    scanner = MarketScanner()
    
    with st.spinner(f"Analizando {chain} (Media móvil {dias_analisis} días)..."):
        try:
            # Pasamos el nuevo parámetro days_window
            df = scanner.scan(chain_filter=chain, min_tvl=min_tvl, days_window=dias_analisis)
            
            if not df.empty:
                st.success(f"¡Análisis completado! Encontrados {len(df)} pools.")
                
                # Nombre dinámico de la columna APR
                col_apr_name = f"APR ({dias_analisis}d)"

                # --- CONFIGURACIÓN VISUAL Y ORDENACIÓN ---
                # Aquí decimos: "Aunque sea un número, muéstralo con %"
                column_config = {
                    "Par": st.column_config.TextColumn("Par", width="medium"),
                    "Red": st.column_config.TextColumn("Red"),
                    "Protocolo": st.column_config.TextColumn("DEX"),
                    "Fee": st.column_config.NumberColumn(
                        "Fee",
                        format="%.2f%%",   # Formato porcentaje con 2 decimales (0.05%)
                        help="Comisión del pool"
                    ),
                    "TVL": st.column_config.NumberColumn(
                        "TVL",
                        format="$%d",      # Formato moneda sin decimales
                    ),
                    col_apr_name: st.column_config.NumberColumn(
                        "APR Media",
                        format="%.1f%%"    # Porcentaje 1 decimal
                    ),
                    "Volatilidad": st.column_config.NumberColumn(
                        "Volatilidad",
                        format="%.1f%%"
                    ),
                    "Costo Riesgo": st.column_config.NumberColumn(
                        "Riesgo IL",
                        format="%.1f%%"
                    ),
                    "Margen": st.column_config.NumberColumn(
                        "Margen",
                        format="%.1f%%"
                    ),
                    "Veredicto": st.column_config.TextColumn("Veredicto")
                }
                
                # Mostramos la tabla con la configuración aplicada
                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config=column_config
                )
                
                st.markdown(f"""
                **Detalles del reporte:**
                * **Fee:** Nivel de comisión del pool (ej. 0.30% es estándar, 0.01% es stable).
                * **APR ({dias_analisis}d):** Rendimiento promedio en los últimos {dias_analisis} días.
                * **Volatilidad:** Fluctuación del precio nativo (Ratio A/B) anualizada.
                """)
            else:
                st.warning(f"No se encontraron pools en {chain} con TVL > ${min_tvl:,.0f}")
                
        except Exception as e:
            st.error(f"Ocurrió un error crítico: {e}")

else:
    st.info("👈 Configura los filtros y pulsa 'Escanear Mercado'.")
