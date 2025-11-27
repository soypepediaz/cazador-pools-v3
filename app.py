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
    st.title("🦄 Cazador de Oportunidades (mucho) Pools")
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
    
    st.sidebar.subheader("Estrategia")
    # Selector de Desviaciones Típicas (SD)
    sd_mult = st.sidebar.slider("Amplitud (Desviaciones Típicas)", 0.1, 3.0, 1.0, step=0.1)
    
    # Rebalanceo
    auto_rebalance = st.sidebar.checkbox("Auto-Rebalancear si sale de rango", value=False)
    if auto_rebalance:
        st.sidebar.caption("⚠️ Se asume un coste de swap del 0.3% en cada rebalanceo.")
    
    # --- Ejecución ---
    if st.button("🚀 Ejecutar Simulación Histórica"):
        
        address = pool.get('Address')
        
        if not address:
            st.error("Error: Falta la dirección del contrato. Vuelve a escanear.")
        else:
            with st.spinner("Calculando volatilidad y simulando..."):
                provider = DataProvider()
                tester = Backtester()
                
                # 1. Bajamos la historia
                pool_full_data = provider.get_pool_history(address)
                history_list = pool_full_data.get('history', [])
                
                # 2. Estimación de Fee Tier (solo para logging si hace falta, ya no se usa en cálculo directo)
                fee_estimado = 0.003 
                if "0.05%" in str(pool['Par']): fee_estimado = 0.0005
                elif "0.01%" in str(pool['Par']): fee_estimado = 0.0001
                elif "1%" in str(pool['Par']): fee_estimado = 0.01
                elif "0.3%" in str(pool['Par']): fee_estimado = 0.003
                
                # 3. Ejecutar simulación
                df_res, min_p, max_p, meta = tester.run_simulation(
                    history_list, 
                    inversion, 
                    sd_mult, 
                    days=dias_sim, 
                    fee_tier=fee_estimado,
                    auto_rebalance=auto_rebalance
                )
                
                if df_res is not None and not df_res.empty:
                    st.success(f"Simulación completada con Volatilidad Anual: **{meta['volatility']*100:.1f}%**")
                    
                    # --- RESULTADOS ---
                    res_final = df_res.iloc[-1]
                    roi_v3 = (res_final['Valor Total'] - inversion) / inversion
                    roi_hodl = (res_final['HODL Value'] - inversion) / inversion
                    
                    # Eliminada la 4ª métrica de Eficiencia
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Valor Final (V3)", f"${res_final['Valor Total']:,.0f}", delta=f"{roi_v3*100:.2f}%")
                    k2.metric("Valor si HODL", f"${res_final['HODL Value']:,.0f}", delta=f"{roi_hodl*100:.2f}%")
                    k3.metric("Fees Totales", f"${res_final['Fees Acum']:,.2f}")
                    
                    if auto_rebalance:
                        st.info(f"🔄 Se realizaron **{meta['rebalances']} rebalanceos** durante el periodo.")

                    # Explicación del rango calculado
                    precio_entrada = df_res.iloc[0]['Price']
                    rango_pct = meta['range_width_pct'] * 100
                    st.info(f"""
                    **Rango Calculado:** ±{rango_pct:.1f}% (Basado en {sd_mult} SD).  
                    Precio entrada: **{precio_entrada:.4f}**. Límites iniciales: **{min_p:.4f}** - **{max_p:.4f}**.
                    """)

                    # --- GRÁFICOS ---
                    
                    # 1. Rendimiento
                    st.subheader("💰 Rendimiento Acumulado")
                    fig_rend = px.line(df_res, x='Date', y=['Valor Total', 'HODL Value'], 
                                       color_discrete_map={"Valor Total": "#00CC96", "HODL Value": "#EF553B"},
                                       labels={"value": "Valor (USD)", "variable": "Estrategia"})
                    st.plotly_chart(fig_rend, use_container_width=True)
                    
                    # 2. Precio y Rangos
                    st.subheader("📊 Precio y Estado")
                    
                    # Coloreamos puntos según estado
                    df_res['Estado'] = df_res['In Range'].apply(lambda x: '🟢 En Rango' if x else '🔴 Fuera de Rango')
                    
                    fig_price = px.scatter(df_res, x='Date', y='Price', color='Estado',
                                           color_discrete_map={'🟢 En Rango': 'green', '🔴 Fuera de Rango': 'red'})
                    
                    # Línea de fondo
                    fig_price.add_traces(px.line(df_res, x='Date', y='Price').update_traces(line=dict(color='lightgray', width=1)).data[0])
                    
                    if not auto_rebalance:
                        fig_price.add_hline(y=min_p, line_dash="dash", line_color="red")
                        fig_price.add_hline(y=max_p, line_dash="dash", line_color="green")
                    else:
                        fig_price.add_traces(px.line(df_res, x='Date', y='Range Min').update_traces(line=dict(color='red', dash='dash')).data[0])
                        fig_price.add_traces(px.line(df_res, x='Date', y='Range Max').update_traces(line=dict(color='green', dash='dash')).data[0])

                    st.plotly_chart(fig_price, use_container_width=True)
                    
                    # --- TABLA DETALLADA MEJORADA ---
                    with st.expander("Ver tabla de datos detallada", expanded=True):
                        # Ordenar columnas para que se vean bien
                        cols_to_show = [
                            "Date", "Price", "Range Min", "Range Max", "In Range", 
                            "APR Period", "Fees Period", "Fees Acum", 
                            "Valor Principal", "Valor Total", "HODL Value"
                        ]
                        
                        st.dataframe(
                            df_res[cols_to_show],
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Date": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
                                "Price": st.column_config.NumberColumn("Precio", format="%.4f"),
                                "Range Min": st.column_config.NumberColumn("Min", format="%.4f"),
                                "Range Max": st.column_config.NumberColumn("Max", format="%.4f"),
                                "APR Period": st.column_config.NumberColumn("APR (8h)", format="%.2f%%"), # Nueva columna formateada
                                "Fees Period": st.column_config.NumberColumn("Fees (8h)", format="$%.2f"), # Nueva columna formateada
                                "Fees Acum": st.column_config.NumberColumn("Fees Total", format="$%.2f"),
                                "Valor Principal": st.column_config.NumberColumn("Principal", format="$%.2f"),
                                "Valor Total": st.column_config.NumberColumn("Total", format="$%.2f"),
                                "HODL Value": st.column_config.NumberColumn("HODL", format="$%.2f"),
                                "In Range": st.column_config.CheckboxColumn("En Rango"), # Checkbox limpio en vez de True/False
                            }
                        )
                        
                else:
                    st.error("Datos insuficientes para simular.")
