import streamlit as st
import pandas as pd
import plotly.express as px
import importlib
import time
import json

# --- RECARGA DE MÓDULOS ---
# Esto es vital para que pille los cambios en math_core y analyzer sin reiniciar el servidor
import uni_v3_kit.analyzer
import uni_v3_kit.data_provider
import uni_v3_kit.backtester
import uni_v3_kit.math_core
import uni_v3_kit.nft_gate

importlib.reload(uni_v3_kit.math_core)
importlib.reload(uni_v3_kit.analyzer)
importlib.reload(uni_v3_kit.data_provider)
importlib.reload(uni_v3_kit.backtester)
importlib.reload(uni_v3_kit.nft_gate)

from uni_v3_kit.analyzer import MarketScanner
from uni_v3_kit.data_provider import DataProvider
from uni_v3_kit.backtester import Backtester
from uni_v3_kit.nft_gate import check_access, verify_signature

st.set_page_config(page_title="Cazador V3", layout="wide", initial_sidebar_state="collapsed")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none;}
    .main .block-container {padding-top: 2rem; max-width: 1200px;}
    h1 {text-align: center; color: #FF4B4B; font-weight: 800;}
    .stButton button {width: 100%; border-radius: 8px; font-weight: bold; height: 3rem;}
    
    .login-box {
        max-width: 400px;
        margin: 40px auto;
        padding: 30px;
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE ESTADO ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'wallet_address' not in st.session_state: st.session_state.wallet_address = ""
if 'step' not in st.session_state: st.session_state.step = 'home'
if 'scan_params' not in st.session_state: st.session_state.scan_params = {}
if 'scan_results' not in st.session_state: st.session_state.scan_results = None
if 'selected_pool' not in st.session_state: st.session_state.selected_pool = None

def go_home():
    st.session_state.step = 'home'
    st.session_state.scan_results = None

def go_to_results(df):
    st.session_state.scan_results = df
    st.session_state.step = 'results'

def go_to_lab(pool_row):
    st.session_state.selected_pool = pool_row
    st.session_state.step = 'lab'

# --- LÓGICA DE LOGIN (Captura de URL) ---
# Esta parte lee los parámetros que nos manda el JS tras firmar
params = st.query_params
if not st.session_state.authenticated and "sig" in params and "addr" in params:
    sig = params["sig"]
    addr = params["addr"]
    
    # Limpiamos URL inmediatamente
    st.query_params.clear()
    
    with st.spinner("Verificando firma en la blockchain..."):
        if verify_signature(addr, sig):
            has_access, msg = check_access(addr)
            if has_access:
                st.session_state.authenticated = True
                st.session_state.wallet_address = addr
                st.success(f"¡Bienvenido! {msg}")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Acceso denegado: {msg}")
        else:
            st.error("Firma inválida.")

# ==========================================
# 0. PANTALLA DE LOGIN
# ==========================================
if not st.session_state.authenticated:
    st.title("🔒 Acceso Token-Gated")
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("""
        <div class="login-box">
            <h3>Conectar Wallet</h3>
            <p style="color: #666;">Firma gratuita para verificar tu NFT en <b>Arbitrum</b>.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # BOTÓN HTML PURO (Sin dependencias de Python)
        # Esto ejecuta JS nativo en el navegador del usuario y redirige a la misma página con los datos en la URL
        components_html = """
        <html>
            <head>
                <style>
                    button {
                        background-color: #FF4B4B; color: white; border: none; 
                        padding: 14px 28px; border-radius: 8px; font-size: 16px; 
                        font-weight: bold; cursor: pointer; width: 100%;
                        transition: background 0.3s;
                    }
                    button:hover { background-color: #ff3333; }
                    p { font-family: sans-serif; color: #666; text-align: center; margin-top: 10px; font-size: 14px; }
                </style>
            </head>
            <body>
                <div style="display: flex; justify-content: center; flex-direction: column; align-items: center;">
                    <button id="connectBtn">🦊 Conectar Metamask</button>
                    <p id="status"></p>
                </div>

                <script>
                    const btn = document.getElementById('connectBtn');
                    const status = document.getElementById('status');

                    btn.addEventListener('click', async () => {
                        if (typeof window.ethereum === 'undefined') {
                            status.innerText = 'Error: No se detectó Metamask. Instala la extensión.';
                            alert('No se detectó Metamask. Por favor instálalo.');
                            return;
                        }

                        status.innerText = 'Abriendo Metamask...';

                        try {
                            // 1. Conectar
                            const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                            const account = accounts[0];
                            
                            // 2. Mensaje
                            const msg = "Acceso a Cazador V3";
                            const msgHex = '0x' + Array.from(msg).map(c => c.charCodeAt(0).toString(16)).join('');
                            
                            status.innerText = 'Solicitando firma...';
                            
                            // 3. Firmar
                            const signature = await window.ethereum.request({
                                method: 'personal_sign',
                                params: [msgHex, account],
                            });
                            
                            status.innerText = 'Verificando...';

                            // 4. Redirigir a la app con los datos en la URL
                            // Usamos window.top.location para salir del iframe de Streamlit
                            const currentUrl = new URL(window.top.location.href);
                            currentUrl.searchParams.set('addr', account);
                            currentUrl.searchParams.set('sig', signature);
                            window.top.location.href = currentUrl.toString();

                        } catch (error) {
                            console.error(error);
                            status.innerText = 'Error: ' + error.message;
                        }
                    });
                </script>
            </body>
        </html>
        """
        
        st.components.v1.html(components_html, height=150)
        
    st.stop()

# ==========================================
# APP PRINCIPAL
# ==========================================

# BARRA SUPERIOR
col_logo, col_user = st.columns([8, 2])
with col_user:
    short_w = f"{st.session_state.wallet_address[:6]}...{st.session_state.wallet_address[-4:]}"
    if st.button(f"🔓 Salir ({short_w})", key="logout_btn"):
        st.session_state.authenticated = False
        st.session_state.wallet_address = ""
        st.rerun()

# 1. INICIO
if st.session_state.step == 'home':
    st.title("🦄 Cazador de Oportunidades Uniswap V3")
    st.markdown("---")
    
    c1, c2, c3 = st.columns([1, 3, 1])
    with c2:
        st.subheader("¿Qué quieres hacer hoy?")
        modo = st.radio("", ["🔍 Escanear Mercado (Búsqueda Avanzada)", "🎯 Analizar un Pool Específico (por contrato)"], label_visibility="collapsed")
        st.write("") 
        
        # OPCIÓN A: ESCÁNER
        if modo == "🔍 Escanear Mercado (Búsqueda Avanzada)":
            with st.form("scanner_form"):
                st.markdown("### ⚙️ Configuración del Escáner")
                
                @st.cache_data(ttl=3600)
                def get_chains():
                    p = DataProvider(); 
                    try: return sorted(list({x.get('ChainId') for x in p.get_all_pools() if x.get('ChainId')}))
                    except: return ["ethereum", "arbitrum", "base", "bsc"]
                
                chains = st.multiselect("Redes (Deja vacío para todas)", get_chains(), default=[])
                
                c_a, c_b = st.columns(2)
                with c_a:
                    min_tvl = st.number_input("TVL Mínimo ($)", value=250000, step=50000)
                    dias_window = st.slider("Ventana Análisis (Días)", 3, 30, 7, help="Días para calcular medias.")
                
                with c_b:
                    min_apr = st.number_input("APR Mínimo (%)", value=10.0, step=1.0)
                    sd_mult = st.slider("Factor Rango (SD)", 0.1, 3.0, 1.0, step=0.1, help="Amplitud para calcular el IL de salida.")

                st.markdown("**Filtrar por Activos:**")
                assets = ["BTC", "ETH", "SOL", "HYPE", "BNB", "Otro"]
                selected_assets = []
                cols_assets = st.columns(6)
                for i, asset in enumerate(assets):
                    if cols_assets[i].checkbox(asset): selected_assets.append(asset)
                
                custom_asset = None
                if "Otro" in selected_assets:
                    custom_asset = st.text_input("Escribe el símbolo (ej: PEPE, USDC):")

                st.markdown("---")
                submitted = st.form_submit_button("🚀 Escanear Mercado")
                
                if submitted:
                    scanner = MarketScanner()
                    with st.spinner("Analizando pools... esto puede tardar unos segundos"):
                        target_chains = chains if chains else None
                        
                        df = scanner.scan(
                            target_chains=target_chains,
                            min_tvl=min_tvl,
                            days_window=dias_window,
                            sd_multiplier=sd_mult,
                            min_apr=min_apr,
                            selected_assets=selected_assets,
                            custom_asset=custom_asset
                        )
                        
                        if not df.empty:
                            st.session_state.scan_params = {'dias': dias_window, 'sd': sd_mult}
                            go_to_results(df)
                            st.rerun()
                        else:
                            st.error("No se encontraron pools con esos criterios.")

        # OPCIÓN B: MANUAL
        else: 
            with st.form("manual_form"):
                st.markdown("### 🎯 Análisis Directo")
                address = st.text_input("Dirección del Contrato (0x...):")
                c_a, c_b = st.columns(2)
                with c_a: dias_window = st.slider("Ventana Análisis (Días)", 3, 30, 7)
                with c_b: sd_mult = st.slider("Factor Rango (SD)", 0.1, 3.0, 1.0)
                
                if st.form_submit_button("🔎 Analizar Pool"):
                    if not address: st.error("Introduce una dirección.")
                    else:
                        scanner = MarketScanner()
                        with st.spinner("Buscando datos..."):
                            df = scanner.analyze_single_pool(address, days_window, sd_mult)
                            if not df.empty:
                                st.session_state.scan_params = {'dias': dias_window, 'sd': sd_mult}
                                go_to_results(df)
                                st.rerun()
                            else: st.error("No se encontraron datos.")

# 2. RESULTADOS
elif st.session_state.step == 'results':
    c_back, c_title = st.columns([1, 6])
    c_back.button("⬅️ Inicio", on_click=go_home)
    c_title.subheader("📊 Resultados del Análisis")
    
    df = st.session_state.scan_results
    dias = st.session_state.scan_params.get('dias', 7)
    sd = st.session_state.scan_params.get('sd', 1.0)
    
    st.info(f"**Criterio:** Fees Probables ({dias}d) vs Riesgo Salida ({sd} SD). Ordenado por Ratio F/IL.")
    
    df_display = df.copy()
    col_apr = [c for c in df_display.columns if "APR (" in c][0]
    df_display[col_apr] = df_display[col_apr] * 100
    
    st.dataframe(df_display, use_container_width=True, hide_index=True, column_config={
        "Address": None, "TVL": st.column_config.NumberColumn(format="$%d"),
        col_apr: st.column_config.NumberColumn(format="%.1f%%"),
        "Volatilidad": st.column_config.NumberColumn(format="%.1f%%"),
        "Rango Est.": st.column_config.NumberColumn("Rango (±%)", format="%.1f%%"),
        "Est. Fees": st.column_config.NumberColumn(f"Fees Prob.", format="%.2f%%"),
        "IL": st.column_config.NumberColumn("IL (Riesgo)", format="%.2f%%"),
        "Ratio F/IL": st.column_config.NumberColumn("Ratio F/IL", format="%.2f", help="Mayor es mejor"),
        "Margen": None 
    })
    
    st.subheader("🧪 Pasar al Laboratorio")
    c1, c2 = st.columns([3, 1])
    with c1:
        df_d = df.reset_index(drop=True)
        def format_option(idx):
            row = df_d.iloc[idx]
            return f"{row['Par']} ({row['DEX']} - {row['Red']}) | Ratio: {row['Ratio F/IL']:.2f}"
        sel_idx = st.selectbox("Pool:", options=df_d.index, format_func=format_option)
    with c2:
        st.write(""); st.write("")
        if st.button("Analizar ➡️", use_container_width=True):
            go_to_lab(df_d.iloc[sel_idx]); st.rerun()

# 3. LABORATORIO
elif st.session_state.step == 'lab':
    pool = st.session_state.selected_pool
    st.button("⬅️ Volver", on_click=lambda: setattr(st.session_state, 'step', 'results'))
    st.title(f"🧪 Lab: {pool['Par']}")
    col_apr_lab = [c for c in pool.index if "APR (" in c][0]
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("DEX", pool['DEX'])
    c2.metric("TVL", f"${pool['TVL']:,.0f}")
    val_apr = pool[col_apr_lab] * 100
    c3.metric("APR", f"{val_apr:.1f}%")
    c4.metric("Volatilidad", f"{pool['Volatilidad']:.1f}%")
    
    st.markdown("---")
    with st.container():
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("⚙️ Simulación")
            inv = st.number_input("Inversión ($)", 1000)
            d_sim = st.slider("Días Simulación", 7, 180, 30)
        with c2:
            st.subheader("🎯 Estrategia")
            sd = st.slider("Rango (SD)", 0.1, 3.0, st.session_state.scan_params.get('sd', 1.0))
            vol_d = st.slider("Ventana Volatilidad", 3, 30, st.session_state.scan_params.get('dias', 7))
            reb = st.checkbox("Auto-Rebalancear", False)
            
    if st.button("🚀 Ejecutar", use_container_width=True):
        addr = pool.get('Address')
        if not addr: st.error("Error dirección")
        else:
            with st.spinner("Simulando..."):
                prov = DataProvider()
                back = Backtester()
                hist = prov.get_pool_history(addr).get('history', [])
                
                fee = 0.003
                if "0.05%" in str(pool['Par']): fee = 0.0005
                elif "0.01%" in str(pool['Par']): fee = 0.0001
                
                df_r, min_p, max_p, meta = back.run_simulation(hist, inv, sd, d_sim, vol_d, fee, reb)
                
                if df_r is not None and not df_r.empty:
                    last = df_r.iloc[-1]
                    roi_v3 = (last['Valor Total'] - inv)/inv
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Final V3", f"${last['Valor Total']:,.0f}", delta=f"{roi_v3*100:.2f}%")
                    k2.metric("Fees", f"${last['Fees Acum']:,.2f}")
                    k3.metric("Rebalanceos", meta['rebalances'])
                    
                    st.info(f"Rango Inicial: ±{meta['initial_range_width_pct']*100:.1f}%.")
                    
                    fig = px.line(df_r, x='Date', y=['Valor Total', 'HODL Value'], title="Rendimiento")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    with st.expander("Detalle"):
                        cols = ["Date", "Price", "Range Min", "Range Max", "Range Width %", "APR Period", "Fees Period", "Valor Total"]
                        st.dataframe(df_r[cols], use_container_width=True)
                else: st.error("Datos insuficientes.")
