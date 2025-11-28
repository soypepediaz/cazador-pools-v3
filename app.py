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
    
    @st.cache_data(ttl=3600)
    def get_chains_disponibles():
        provider = DataProvider()
        try:
            pools = provider.get_all_pools()
            chains = {pool.get('ChainId') for pool in pools if pool.get('ChainId')}
            return sorted(list(chains))
        except: return ["ethereum", "base", "bsc", "arbitrum"]

    # --- SIDEBAR: CONFIGURACIÓN GLOBAL ---
    st.sidebar.header("⚙️ Configuración de Estrategia")
    st.sidebar.info("Estos parámetros definen el criterio de **Veredicto** (Gema/Rekt) tanto para el Escáner como para la Búsqueda Manual.")
    
    dias_analisis = st.sidebar.slider("Ventana Análisis (Días)", 3, 30, 7, help="Días pasados para calcular volatilidad y días futuros para proyectar fees.")
    sd_mult = st.sidebar.slider("Factor Rango (SD)", 0.1, 3.0, 1.0, step=0.1, help="Amplitud del rango basada en Desviaciones Típicas.")

    st.sidebar.markdown("---")

    # --- SIDEBAR: BÚSQUEDA MANUAL ---
    st.sidebar.header("🔍 Búsqueda Manual")
    manual_address = st.sidebar.text_input("Dirección del Pool (0x...)", placeholder="Pega el contrato aquí")
    
    # Botón justo debajo del input
    if st.sidebar.button("Analizar Pool Concreto"):
        if manual_address:
            scanner = MarketScanner()
            with st.spinner("Analizando dirección específica..."):
                try:
                    # Pasamos los parámetros globales de estrategia
                    df = scanner.analyze_single_pool(manual_address, days_window=dias_analisis, sd_multiplier=sd_mult)
                    if not df.empty:
                        st.session_state.scan_results = df
                        st.success("Pool encontrado.")
                    else: st.error("No se encontraron datos para esa dirección.")
                except Exception as e: st.error(f"Error: {e}")
        else: st.sidebar.warning("Introduce una dirección.")

    st.sidebar.markdown("---")

    # --- SIDEBAR: ESCÁNER MASIVO ---
    st.sidebar.header("🎯 Escáner de Mercado")
    chain = st.sidebar.selectbox("Red", get_chains_disponibles())
    min_tvl = st.sidebar.number_input("Liquidez Mínima ($)", value=50000, step=10000)

    if st.sidebar.button("🔍 Escanear Mercado"):
        scanner = MarketScanner()
        with st.spinner(f"Escaneando {chain}..."):
            try:
                # Pasamos los parámetros globales de estrategia
                df = scanner.scan(chain, min_tvl, days_window=dias_analisis, sd_multiplier=sd_mult)
                st.session_state.scan_results = df
                if df.empty: st.warning("Sin resultados.")
                else: st.success(f"Encontrados {len(df)} pools.")
            except Exception as e: st.error(f"Error: {e}")

    # --- RESULTADOS ---
    if st.session_state.scan_results is not None and not st.session_state.scan_results.empty:
        # Trabajamos sobre una copia para no alterar los datos originales del estado
        df_display = st.session_state.scan_results.copy()
        
        # Nombre dinámico APR
        col_apr = [c for c in df_display.columns if "APR (" in c][0]
        
        # FIX VISUAL: Multiplicamos APR por 100 para que coincida con el formato %.1f%%
        # (Si el dato es 0.8, ahora será 80.0, y se mostrará como 80.0%)
        df_display[col_apr] = df_display[col_apr] * 100
        
        # Mensaje explicativo sobre el criterio usado
        st.info(f"""
        **Criterio de Veredicto:** Se compara si las FEES estimadas en **{dias_analisis} días** superan el RIESGO DE SALIDA (IL) de un rango de **{sd_mult} SD**.
        """)

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Address": None, 
                "TVL": st.column_config.NumberColumn(format="$%d"),
                col_apr: st.column_config.NumberColumn(format="%.1f%%"), 
                "Volatilidad": st.column_config.NumberColumn(format="%.1f%%"),
                "Rango Est.": st.column_config.NumberColumn("Rango (±%)", format="%.1f%%"),
                "Est. Fees": st.column_config.NumberColumn(f"Fees Est. ({dias_analisis}d)", format="%.2f%%"),
                "Max IL": st.column_config.NumberColumn("Riesgo Salida", format="%.2f%%"),
                "Margen": None 
            }
        )
        
        st.markdown("---")
        st.subheader("🧪 Pasar al Laboratorio")
        
        c1, c2 = st.columns([3, 1])
        with c1:
            # Selector inteligente con nombre y DEX
            # Usamos el dataframe original (sin multiplicar) para mantener consistencia interna si hiciera falta
            # pero para el display usamos el índice que es el mismo.
            def format_option(idx):
                row = st.session_state.scan_results.iloc[idx]
                return f"{row['Par']} ({row['DEX']})"
            
            seleccion_idx = st.selectbox(
                "Selecciona un pool para hacer Backtesting:",
                options=st.session_state.scan_results.index,
                format_func=format_option
            )
        
        with c2:
            st.write("") 
            st.write("") 
            if st.button("Analizar Pool ➡️"):
                if seleccion_idx is not None:
                    row = st.session_state.scan_results.iloc[seleccion_idx]
                    go_to_lab(row)
                    st.rerun()

    elif st.session_state.scan_results is not None: st.info("No hay resultados.")
    else: st.info("Usa la barra lateral para buscar un pool o escanear el mercado.")

# ==========================================
# VISTA 2: LABORATORIO
# ==========================================
elif st.session_state.view == 'lab':
    pool = st.session_state.selected_pool
    st.button("⬅️ Volver", on_click=go_to_scanner)
    
    st.title(f"🧪 Laboratorio: {pool['Par']}")
    col_apr_lab = [c for c in pool.index if "APR (" in c][0]
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("DEX", f"{pool['DEX']} ({pool['Red']})") 
    c2.metric("TVL", f"${pool['TVL']:,.0f}")
    # CORRECCIÓN VISUAL: Multiplicamos por 100 si el valor viene en decimal (0.8)
    val_apr = pool[col_apr_lab]
    c3.metric("APR Media", f"{val_apr*100:.1f}%") 
    c4.metric("Volatilidad", f"{pool['Volatilidad']:.1f}%") 
    
    st.markdown("---")
    
    # --- Config ---
    st.sidebar.header("⚙️ Simulación")
    inversion = st.sidebar.number_input("Inversión ($)", 1000, 1000000, 10000)
    
    dias_sim = st.sidebar.slider("Días a Simular", 7, 180, 30)
    vol_days = st.sidebar.slider("Ventana Volatilidad", 3, 30, 7)
    
    st.sidebar.subheader("Estrategia")
    sd_mult = st.sidebar.slider("Amplitud (SD)", 0.1, 3.0, 1.0, step=0.1)
    
    auto_rebalance = st.sidebar.checkbox("Auto-Rebalancear", value=False)
    if auto_rebalance: st.sidebar.caption("⚠️ Coste swap: 0.3%")
    
    if st.button("🚀 Ejecutar Simulación"):
        address = pool.get('Address')
        if not address: st.error("Falta Address.")
        else:
            with st.spinner("Simulando..."):
                provider = DataProvider()
                tester = Backtester()
                history_data = provider.get_pool_history(address).get('history', [])
                
                fee_est = 0.003
                
                df_res, min_p, max_p, meta = tester.run_simulation(
                    history_data, inversion, sd_mult, 
                    sim_days=dias_sim, vol_days=vol_days, 
                    fee_tier=fee_est, auto_rebalance=auto_rebalance
                )
                
                if df_res is not None and not df_res.empty:
                    last = df_res.iloc[-1]
                    roi_v3 = (last['Valor Total'] - inversion) / inversion
                    roi_hodl = (last['HODL Value'] - inversion) / inversion
                    
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Valor Final (V3)", f"${last['Valor Total']:,.0f}", delta=f"{roi_v3*100:.2f}%")
                    k2.metric("Valor si HODL", f"${last['HODL Value']:,.0f}", delta=f"{roi_hodl*100:.2f}%")
                    k3.metric("Fees Totales", f"${last['Fees Acum']:,.2f}")
                    
                    if auto_rebalance: st.info(f"🔄 **{meta['rebalances']} rebalanceos** realizados.")

                    precio_ini = df_res.iloc[0]['Price']
                    rango_pct = meta['initial_range_width_pct'] * 100
                    st.info(f"**Rango Inicial:** ±{rango_pct:.1f}%. Entrada: **{precio_ini:.4f}**. Límites: **{min_p:.4f}** - **{max_p:.4f}**")

                    st.subheader("💰 Rendimiento")
                    fig_rend = px.line(df_res, x='Date', y=['Valor Total', 'HODL Value'], 
                                       color_discrete_map={"Valor Total": "#00CC96", "HODL Value": "#EF553B"})
                    st.plotly_chart(fig_rend, use_container_width=True)
                    
                    st.subheader("📊 Precio y Rangos")
                    df_res['Estado'] = df_res['In Range'].apply(lambda x: '🟢 En Rango' if x else '🔴 Fuera')
                    df_res['Ancho Rango'] = df_res['Range Width %'].apply(lambda x: f"±{x:.1f}%")

                    fig_price = px.scatter(df_res, x='Date', y='Price', color='Estado',
                                           color_discrete_map={'🟢 En Rango': 'green', '🔴 Fuera': 'red'},
                                           hover_data={'Ancho Rango': True})
                    fig_price.add_traces(px.line(df_res, x='Date', y='Price').update_traces(line=dict(color='lightgray', width=1)).data[0])
                    
                    if not auto_rebalance:
                        fig_price.add_hline(y=min_p, line_dash="dash", line_color="red")
                        fig_price.add_hline(y=max_p, line_dash="dash", line_color="green")
                    else:
                        line_min = px.line(df_res, x='Date', y='Range Min', hover_data={'Ancho Rango': True})
                        line_min.update_traces(line=dict(color='red', dash='dash'))
                        fig_price.add_traces(line_min.data[0])
                        
                        line_max = px.line(df_res, x='Date', y='Range Max', hover_data={'Ancho Rango': True})
                        line_max.update_traces(line=dict(color='green', dash='dash'))
                        fig_price.add_traces(line_max.data[0])

                    st.plotly_chart(fig_price, use_container_width=True)
                    
                    with st.expander("Ver detalle"):
                        cols = ["Date", "Price", "Range Min", "Range Max", "Range Width %", "APR Period", "Fees Period", "Valor Total"]
                        
                        st.dataframe(
                            df_res[cols],
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Date": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
                                "Price": st.column_config.NumberColumn("Precio", format="%.4f"),
                                "Range Min": st.column_config.NumberColumn("Min", format="%.4f"),
                                "Range Max": st.column_config.NumberColumn("Max", format="%.4f"),
                                "Range Width %": st.column_config.NumberColumn("Ancho (±%)", format="%.2f %%"),
                                "APR Period": st.column_config.NumberColumn("APR (8h)", format="%.2f%%"),
                                "Fees Period": st.column_config.NumberColumn("Fees (8h)", format="$%.2f"),
                                "Fees Acum": st.column_config.NumberColumn("Fees Total", format="$%.2f"),
                                "Valor Principal": st.column_config.NumberColumn("Principal", format="$%.2f"),
                                "Valor Total": st.column_config.NumberColumn("Total", format="$%.2f"),
                                "HODL Value": st.column_config.NumberColumn("HODL", format="$%.2f"),
                            }
                        )
                else: st.error("Datos insuficientes.")
