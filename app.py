import streamlit as st
import pandas as pd
import plotly.express as px
from uni_v3_kit.analyzer import MarketScanner
from uni_v3_kit.data_provider import DataProvider
from uni_v3_kit.backtester import Backtester

st.set_page_config(page_title="Cazador V3 Lab", layout="wide")

# --- GESTIÓN DE NAVEGACIÓN (ESTADO) ---
if 'view' not in st.session_state:
    st.session_state.view = 'scanner'
if 'selected_pool' not in st.session_state:
    st.session_state.selected_pool = None

def go_to_lab(pool_data):
    st.session_state.selected_pool = pool_data
    st.session_state.view = 'lab'

def go_to_scanner():
    st.session_state.view = 'scanner'
    st.session_state.selected_pool = None

# ==========================================
# VISTA 1: ESCÁNER DE MERCADO
# ==========================================
if st.session_state.view == 'scanner':
    st.title("🦄 Cazador de Oportunidades Uniswap V3")
    st.markdown("Encuentra pools rentables y **analízalos a fondo** en el laboratorio.")

    # --- Configuración Sidebar ---
    @st.cache_data(ttl=3600)
    def get_chains_disponibles():
        provider = DataProvider()
        try:
            pools = provider.get_all_pools()
            chains = {pool.get('ChainId') for pool in pools if pool.get('ChainId')}
            return sorted(list(chains))
        except:
            return ["ethereum", "base", "bsc", "arbitrum"]

    st.sidebar.header("🎯 Filtros de Escaneo")
    chain = st.sidebar.selectbox("Red", get_chains_disponibles())
    min_tvl = st.sidebar.number_input("Liquidez Mínima ($)", value=50000, step=10000)
    
    st.sidebar.markdown("---")
    dias_analisis = st.sidebar.slider("Ventana Media Móvil (Días)", 3, 30, 7)

    # --- Ejecución ---
    if st.sidebar.button("🔍 Escanear Mercado"):
        scanner = MarketScanner()
        with st.spinner(f"Analizando {chain}..."):
            try:
                # Nota: Asegúrate de que analyzer.py devuelve la columna 'Address' aunque sea oculta
                df = scanner.scan(chain, min_tvl, dias_analisis)
                
                if not df.empty:
                    st.success(f"Encontrados {len(df)} pools.")
                    
                    # 1. Mostrar Tabla Resumen
                    col_apr = f"APR ({dias_analisis}d)"
                    
                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Address": None, # Ocultamos la dirección técnica
                            "TVL": st.column_config.NumberColumn(format="$%d"),
                            col_apr: st.column_config.NumberColumn(format="%.2f%%"),
                            "Volatilidad": st.column_config.NumberColumn(format="%.1f%%"),
                            "Riesgo IL": st.column_config.NumberColumn(format="%.1f%%"),
                            "Margen": st.column_config.NumberColumn(format="%.1f%%")
                        }
                    )
                    
                    st.markdown("---")
                    st.subheader("🧪 Pasar al Laboratorio")
                    
                    # Selector para elegir qué pool analizar
                    opciones = df['Par'].tolist()
                    seleccion = st.selectbox("Selecciona un pool para hacer Backtesting:", opciones)
                    
                    if st.button("Analizar Pool Seleccionado ➡️"):
                        # Extraemos la fila completa del DF
                        row = df[df['Par'] == seleccion].iloc[0]
                        go_to_lab(row)
                        st.rerun()
                        
                else:
                    st.warning("No se encontraron pools con esos filtros.")
            except Exception as e:
                st.error(f"Error en el escaneo: {e}")

    else:
        st.info("👈 Configura los filtros y pulsa 'Escanear Mercado'.")

# ==========================================
# VISTA 2: LABORATORIO (BACKTESTING)
# ==========================================
elif st.session_state.view == 'lab':
    pool = st.session_state.selected_pool
    
    # Botón Volver
    st.button("⬅️ Volver al Escáner", on_click=go_to_scanner)
    
    st.title(f"🧪 Laboratorio: {pool['Par']}")
    
    # Métricas clave del pool seleccionado
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Protocolo", f"{pool['Protocolo']} ({pool['Red']})")
    c2.metric("TVL", f"${pool['TVL']:,.0f}")
    c3.metric("Volatilidad Real", f"{pool['Volatilidad']:.1f}%")
    c4.metric("Veredicto", pool['Veredicto'])
    
    st.markdown("---")
    
    # --- Configuración Backtest ---
    st.sidebar.header("⚙️ Parámetros de Simulación")
    
    inversion = st.sidebar.number_input("Inversión Inicial ($)", 1000, 1000000, 10000)
    dias_sim = st.sidebar.slider("Días de Historial a simular", 7, 90, 30)
    
    st.sidebar.subheader("Estrategia de Rango")
    st.sidebar.markdown("""
    Define cuánto te alejas del precio actual.
    * **Estrecho (±5-10%):** Más fees, alto riesgo de salir de rango.
    * **Amplio (±20-50%):** Menos fees, posición más pasiva.
    """)
    rango_width = st.sidebar.slider("Amplitud del Rango (±%)", 5, 100, 20) / 100.0
    
    # --- Ejecución ---
    if st.button("🚀 Ejecutar Simulación Histórica"):
        
        # Recuperamos la dirección del pool (Address) que guardamos en el DF
        address = pool.get('Address')
        
        if not address:
            st.error("Error: No se encontró la dirección del contrato. Asegúrate de actualizar analyzer.py.")
        else:
            with st.spinner("Viajando al pasado y simulando rendimientos..."):
                provider = DataProvider()
                tester = Backtester()
                
                # 1. Bajamos la historia completa
                history = provider.get_pool_history(address)
                
                # 2. Corremos la simulación
                # Nota: analyzer.py nos dio el Fee como 0.003 (decimal) o similar, lo pasamos.
                # Como en el DF final guardamos el fee formateado o procesado, intentamos recuperarlo.
                # Si no, usamos un estándar 0.003 (0.3%) o 0.0005 (0.05%) según el nombre
                fee_estimado = 0.003 
                if "0.05%" in pool['Par']: fee_estimado = 0.0005
                elif "0.01%" in pool['Par']: fee_estimado = 0.0001
                elif "1%" in pool['Par']: fee_estimado = 0.01
                
                df_res, min_p, max_p = tester.run_simulation(
                    history, 
                    inversion, 
                    rango_width, 
                    days=dias_sim, 
                    fee_tier=fee_estimado
                )
                
                if df_res is not None and not df_res.empty:
                    st.success("Simulación finalizada con éxito.")
                    
                    # --- RESULTADOS ---
                    res_final = df_res.iloc[-1]
                    roi_v3 = (res_final['Valor Total'] - inversion) / inversion
                    roi_hodl = (res_final['HODL Value'] - inversion) / inversion
                    
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Valor Final (V3)", f"${res_final['Valor Total']:,.2f}", delta=f"{roi_v3*100:.2f}%")
                    k2.metric("Valor si HODL", f"${res_final['HODL Value']:,.2f}", delta=f"{roi_hodl*100:.2f}%")
                    k3.metric("Fees Ganadas", f"${res_final['Fees Acum']:,.2f}")
                    
                    # --- GRÁFICOS ---
                    st.subheader("Evolución del Portafolio")
                    
                    # Gráfico comparativo V3 vs HODL
                    fig = px.line(df_res, x='Date', y=['Valor Total', 'HODL Value'], 
                                  title="Rendimiento: Estrategia V3 vs HODL",
                                  labels={"value": "Valor en USD", "variable": "Estrategia"})
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Gráfico de Precio y Rangos
                    st.subheader("Precio vs Rango Seleccionado")
                    fig2 = px.line(df_res, x='Date', y='Price', title="Precio del Activo")
                    # Añadimos líneas de rango
                    fig2.add_hline(y=min_p, line_dash="dash", line_color="red", annotation_text="Límite Inferior")
                    fig2.add_hline(y=max_p, line_dash="dash", line_color="green", annotation_text="Límite Superior")
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    # Tabla detalle
                    with st.expander("Ver datos día a día"):
                        st.dataframe(df_res)
                        
                else:
                    st.error("No hay suficientes datos históricos para simular este periodo.")
