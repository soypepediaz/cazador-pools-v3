import streamlit as st
import pandas as pd
import plotly.express as px
import importlib
import time

# --- RECARGAS ---
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
    
    .login-container {
        max-width: 400px;
        margin: 50px auto;
        padding: 2rem;
        border-radius: 12px;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE ESTADO ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'wallet_address' not in st.session_state: st.session_state.wallet_address = ""
if 'step' not in st.session_state: st.session_state.step = 'home'

# --- LÓGICA DE LOGIN WEB3 (URL PARAMS) ---
# Verificamos si venimos de una redirección con firma
params = st.query_params
if not st.session_state.authenticated and "sig" in params and "addr" in params:
    sig = params["sig"]
    addr = params["addr"]
    
    with st.spinner("Verificando firma criptográfica y NFTs..."):
        # 1. Verificar que la firma corresponde a la dirección (Seguridad)
        is_valid_sig = verify_signature(addr, sig)
        
        if is_valid_sig:
            # 2. Verificar si tiene el NFT
            has_access, msg = check_access(addr)
            if has_access:
                st.session_state.authenticated = True
                st.session_state.wallet_address = addr
                st.success("Login correcto.")
                # Limpiamos la URL para que quede bonita
                st.query_params.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Firma válida, pero no tienes el NFT: {msg}")
        else:
            st.error("Firma inválida. No se puede verificar la propiedad de la cuenta.")

# ==========================================
# 0. PANTALLA DE LOGIN
# ==========================================
if not st.session_state.authenticated:
    st.title("🔒 Acceso Token-Gated")
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("""
        <div class="login-container">
            <h3>Conectar Wallet</h3>
            <p>Debes firmar un mensaje para demostrar que posees el NFT de acceso en Arbitrum.</p>
            <div id="wallet-btn-container"></div>
        </div>
        """, unsafe_allow_html=True)
        
        # JAVASCRIPT INJECTION PARA METAMASK
        # Este script crea el botón, conecta, firma y recarga la página con los datos.
        components_html = """
        <script>
        async function connectAndSign() {
            if (typeof window.ethereum === 'undefined') {
                alert('Por favor instala Metamask o Rabby!');
                return;
            }
            
            try {
                // 1. Conectar Wallet
                const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                const account = accounts[0];
                
                // 2. Firmar Mensaje
                const message = "Acceso a Cazador V3";
                // Convertir mensaje a Hex para personal_sign
                const msgHex = '0x' + Array.from(message).map(c => c.charCodeAt(0).toString(16)).join('');
                
                const signature = await window.ethereum.request({
                    method: 'personal_sign',
                    params: [msgHex, account],
                });
                
                // 3. Redirigir a Streamlit con datos
                // Usamos window.top.location para salir del iframe de Streamlit
                const currentUrl = new URL(window.top.location.href);
                currentUrl.searchParams.set('addr', account);
                currentUrl.searchParams.set('sig', signature);
                window.top.location.href = currentUrl.toString();
                
            } catch (error) {
                console.error(error);
                alert('Error al conectar: ' + error.message);
            }
        }
        </script>
        
        <div style="display: flex; justify-content: center;">
            <button onclick="connectAndSign()" style="
                background-color: #FF4B4B; 
                color: white; 
                border: none; 
                padding: 12px 24px; 
                border-radius: 8px; 
                font-size: 16px; 
                font-weight: bold; 
                cursor: pointer;
                width: 100%;
                max-width: 300px;">
                🦊 Conectar & Firmar
            </button>
        </div>
        """
        st.components.v1.html(components_html, height=100)
        
        st.warning("Nota: Asegúrate de estar en la red Arbitrum (o la que uses habitualmente). La firma es gratuita (off-chain).")

    st.stop()

# ==========================================
# APLICACIÓN PRINCIPAL (SOLO SI AUTENTICADO)
# ==========================================

# --- HEADER ---
col_title, col_user = st.columns([6, 2])
with col_title:
    st.title("🦄 Cazador de Oportunidades V3")
with col_user:
    short_w = f"{st.session_state.wallet_address[:6]}...{st.session_state.wallet_address[-4:]}"
    if st.button(f"🔓 Salir ({short_w})", key="logout_btn"):
        st.session_state.authenticated = False
        st.query_params.clear()
        st.rerun()

st.markdown("---")

# --- INICIALIZAR VARIABLES APP ---
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

# ==========================================
# 1. WIZARD INICIO
# ==========================================
if st.session_state.step == 'home':
    c1, c2, c3 = st.columns([1, 3, 1])
    with c2:
        modo = st.radio("", ["🔍 Escanear Mercado", "🎯 Analizar Pool Específico"], horizontal=True)
        st.write("")
        
        if modo == "🔍 Escanear Mercado":
            with st.form("scanner"):
                st.markdown("### ⚙️ Configuración")
                @st.cache_data(ttl=3600)
                def get_chains():
                    p = DataProvider(); 
                    try: return sorted(list({x.get('ChainId') for x in p.get_all_pools() if x.get('ChainId')}))
                    except: return ["ethereum", "arbitrum", "base", "bsc"]
                
                chains = st.multiselect("Redes", get_chains())
                c_a, c_b = st.columns(2)
                with c_a:
                    min_tvl = st.number_input("TVL Min ($)", 250000, step=50000)
                    dias = st.slider("Ventana Análisis (Días)", 3, 30, 7)
                with c_b:
                    min_apr = st.number_input("APR Min (%)", 10.0, step=1.0)
                    sd = st.slider("Rango (SD)", 0.1, 3.0, 1.0, step=0.1)
                
                assets = ["BTC", "ETH", "SOL", "HYPE", "BNB", "Otro"]
                sel_assets = []
                cc = st.columns(6)
                for i, a in enumerate(assets):
                    if cc[i].checkbox(a): sel_assets.append(a)
                
                custom = None
                if "Otro" in sel_assets: custom = st.text_input("Símbolo:")
                
                if st.form_submit_button("🚀 Escanear"):
                    scanner = MarketScanner()
                    with st.spinner("Escaneando..."):
                        target = chains if chains else None
                        df = scanner.scan(target, min_tvl, dias, sd, min_apr, sel_assets, custom)
                        if not df.empty:
                            st.session_state.scan_params = {'dias': dias, 'sd': sd}
                            go_to_results(df)
                            st.rerun()
                        else: st.error("Sin resultados.")
        else:
            with st.form("manual"):
                st.markdown("### 🎯 Análisis")
                addr = st.text_input("Contrato (0x...):")
                c_a, c_b = st.columns(2)
                with c_a: dias = st.slider("Ventana (Días)", 3, 30, 7)
                with c_b: sd = st.slider("Rango (SD)", 0.1, 3.0, 1.0)
                
                if st.form_submit_button("🔎 Analizar"):
                    scanner = MarketScanner()
                    with st.spinner("Buscando..."):
                        df = scanner.analyze_single_pool(addr, dias, sd)
                        if not df.empty:
                            st.session_state.scan_params = {'dias': dias, 'sd': sd}
                            go_to_results(df)
                            st.rerun()
                        else: st.error("No encontrado.")

# ==========================================
# 2. RESULTADOS
# ==========================================
elif st.session_state.step == 'results':
    c_back, c_t = st.columns([1, 6])
    c_back.button("⬅️ Inicio", on_click=go_home)
    c_t.subheader("📊 Resultados")
    
    df = st.session_state.scan_results
    dias = st.session_state.scan_params['dias']
    sd = st.session_state.scan_params['sd']
    
    st.info(f"**Criterio:** Fees Probables ({dias}d) vs Riesgo IL ({sd} SD).")
    
    df_show = df.copy()
    c_apr = [c for c in df_show.columns if "APR (" in c][0]
    df_show[c_apr] = df_show[c_apr] * 100
    
    st.dataframe(df_show, use_container_width=True, hide_index=True, column_config={
        "Address": None, "TVL": st.column_config.NumberColumn(format="$%d"),
        c_apr: st.column_config.NumberColumn(format="%.1f%%"),
        "Volatilidad": st.column_config.NumberColumn(format="%.1f%%"),
        "Rango Est.": st.column_config.NumberColumn("Rango (±%)", format="%.1f%%"),
        "Est. Fees": st.column_config.NumberColumn("Fees Prob.", format="%.2f%%"),
        "IL": st.column_config.NumberColumn("Riesgo IL", format="%.2f%%"),
        "Ratio F/IL": st.column_config.NumberColumn("Ratio", format="%.2f"), "Margen": None
    })
    
    st.subheader("🧪 Laboratorio")
    c1, c2 = st.columns([3, 1])
    with c1:
        df_d = df.reset_index(drop=True)
        sel = st.selectbox("Pool:", df_d.index, format_func=lambda i: f"{df_d.iloc[i]['Par']} ({df_d.iloc[i]['DEX']})")
    with c2:
        st.write(""); st.write("")
        if st.button("Analizar ➡️", use_container_width=True):
            go_to_lab(df_d.iloc[sel]); st.rerun()

# ==========================================
# 3. LABORATORIO
# ==========================================
elif st.session_state.step == 'lab':
    pool = st.session_state.selected_pool
    st.button("⬅️ Volver", on_click=lambda: setattr(st.session_state, 'step', 'results'))
    st.title(f"🧪 {pool['Par']}")
    
    c_apr = [c for c in pool.index if "APR (" in c][0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("DEX", pool['DEX'])
    c2.metric("TVL", f"${pool['TVL']:,.0f}")
    c3.metric("APR", f"{pool[c_apr]*100:.1f}%")
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
