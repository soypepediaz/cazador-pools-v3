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
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None

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

    # --- Ejecución del Escáner ---
    if st.sidebar.button("🔍 Escanear Mercado"):
        scanner = MarketScanner()
        with st.spinner(f"Analizando {chain}..."):
            try:
                # Guardamos el resultado en session_state
                df = scanner.scan(chain, min_tvl, dias_analisis)
                st.session_state.scan_results = df
                
                if df.empty:
                    st.warning("No se encontraron pools con esos filtros.")
                else:
                    st.success(f"Encontrados {len(df)} pools.")
            except Exception as e:
                st.error(f"Error en el escaneo: {e}")

    # --- Renderizado de Resultados ---
    if st.session_state.scan_results is not None and not st.session_state.scan_results.empty:
        df = st.session_state.scan_results
        
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Address": None, # Ocultamos la dirección técnica
                "TVL": st.column_config.NumberColumn(format="$%d"),
                "APR Media": st.column_config.NumberColumn(format="%.1f%%"),
                "Volatilidad": st.column_config.NumberColumn(format="%.1f%%"),
                "Riesgo IL": st.column_config.NumberColumn(format="%.1f%%"),
                "Margen": st.column_config.NumberColumn(format="%.1f%%")
            }
        )
        
        st.markdown("---")
        st.subheader("🧪 Pasar al Laboratorio")
        
        col_sel, col_btn = st.columns([3, 1])
        
        with col_sel:
            opciones = df['Par'].tolist()
            seleccion = st.selectbox("Selecciona un pool para hacer Backtesting:", opciones)
        
        with col_btn:
            st.write("") 
            st.write("") 
            if st.button("Analizar Pool ➡️"):
                if seleccion:
                    # Extraemos la fila completa del DF
                    row = df[df['Par'] == seleccion].iloc[0]
                    go_to_lab(row)
                    st.rerun()

    elif st.session_state.scan_results is not None and st.session_state.scan_results.empty:
        st.info("No hay resultados para mostrar.")
    else:
        st.info("👈 Configura los filtros y pulsa 'Escanear Mercado'.")

# ==========================================
# VISTA 2: LABORATORIO (BACKTESTING)
# ==========================================
elif st.session_state.view == 'lab':
    pool = st.session_state.selected_pool
    
    st.button("⬅️ Volver al Escáner", on_click=go_to_scanner)
    
    st.title(f"🧪 Laboratorio: {pool['Par']}")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Protocolo", f"{pool['DEX']} ({pool['Red']})") 
    c2.metric("TVL", f"${pool['TVL']:,.0f}")
    c3.metric("APR Media", f"{pool['APR Media']:.1f}%")
    c4.metric("Volatilidad", f"{pool['Volatilidad']:.1f}%")
    
    st.markdown("---")
    
    # --- Configuración Backtest ---
    st.sidebar.header("⚙️ Parámetros de Simulación")
    inversion = st.sidebar.number_input("Inversión Inicial ($)", 1000, 1000000, 10000)
    dias_sim = st.sidebar.slider("Días de Historial a simular", 7, 90, 30)
    
    st.sidebar.subheader("Estrategia de Rango")
    st.sidebar.markdown("Definir rango ±% sobre el precio inicial.")
    rango_width = st.sidebar.slider("Amplitud del Rango (±%)", 5, 100, 20) / 100.0
    
    # --- Ejecución ---
    if st.button("🚀 Ejecutar Simulación Histórica"):
        
        address = pool.get('Address')
        
        if not address:
            st.error("Error: Falta la dirección del contrato. Vuelve a escanear.")
        else:
            with st.spinner("Simulando estrategia..."):
                provider = DataProvider()
                tester = Backtester()
                
                # Extraemos la lista 'history' del objeto pool
                pool_full_data = provider.get_pool_history(address)
                history_list = pool_full_data.get('history', [])
                
                # Estimación de Fee Tier
                fee_estimado = 0.003 
                if "0.05%" in str(pool['Par']): fee_estimado = 0.0005
                elif "0.01%" in str(pool['Par']): fee_estimado = 0.0001
                elif "1%" in str(pool['Par']): fee_estimado = 0.01
                elif "0.3%" in str(pool['Par']): fee_estimado = 0.003
                
                # Pasamos la lista limpia al simulador
                df_res, min_p, max_p = tester.run_simulation(
                    history_list, 
                    inversion, 
                    rango_width, 
                    days=dias_sim, 
                    fee_tier=fee_estimado
                )
                
                if df_res is not None and not df_res.empty:
                    st.success("Simulación completada.")
                    
                    # Resultados numéricos
                    res_final = df_res.iloc[-1]
                    roi_v3 = (res_final['Valor Total'] - inversion) / inversion
                    roi_hodl = (res_final['HODL Value'] - inversion) / inversion
                    
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Valor Final (V3)", f"${res_final['Valor Total']:,.2f}", delta=f"{roi_v3*100:.2f}%")
                    k2.metric("Valor si HODL", f"${res_final['HODL Value']:,.2f}", delta=f"{roi_hodl*100:.2f}%")
                    k3.metric("Fees Ganadas", f"${res_final['Fees Acum']:,.2f}")
                    
                    # --- 1. EXPLICACIÓN DEL RANGO ---
                    precio_entrada = df_res.iloc[0]['Price']
                    st.info(f"""
                    **Análisis del Rango Seleccionado:** Has configurado una amplitud de **±{rango_width*100:.0f}%**.  
                    Con un precio de entrada de **{precio_entrada:.4f}**, tu posición gana comisiones solo si el precio se mantiene entre **{min_p:.4f}** y **{max_p:.4f}**.
                    """)

                    # --- 2. GRÁFICO RENDIMIENTO ---
                    st.subheader("💰 Rendimiento Acumulado")
                    fig = px.line(df_res, x='Date', y=['Valor Total', 'HODL Value'], 
                                  color_discrete_map={"Valor Total": "#00CC96", "HODL Value": "#EF553B"},
                                  labels={"value": "Valor (USD)", "variable": "Estrategia"})
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # --- 3. GRÁFICO PRECIO VS RANGO ---
                    st.subheader("📊 Precio vs Rango")
                    
                    # Creamos columna Estado
                    df_res['Estado'] = df_res['In Range'].apply(lambda x: '🟢 Cobrando Fees' if x else '🔴 Fuera de Rango')
                    
                    fig2 = px.scatter(df_res, x='Date', y='Price', color='Estado',
                                      color_discrete_map={'🟢 Cobrando Fees': 'green', '🔴 Fuera de Rango': 'red'},
                                      title="Evolución del Precio y Estado de la Posición")
                    
                    fig2.add_traces(px.line(df_res, x='Date', y='Price').update_traces(line=dict(color='lightgray', width=1)).data[0])
                    
                    # Líneas de Rango
                    fig2.add_hline(y=min_p, line_dash="dash", line_color="red", annotation_text=f"Min: {min_p:.4f}")
                    fig2.add_hline(y=max_p, line_dash="dash", line_color="green", annotation_text=f"Max: {max_p:.4f}")
                    
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    with st.expander("Ver tabla de datos detallada"):
                        st.dataframe(df_res)
                        
                else:
                    st.error("No hay suficientes datos históricos para este pool.")
