from .data_provider import DataProvider
from .math_core import V3Math
import pandas as pd

class MarketScanner:
    def __init__(self):
        self.data = DataProvider()
        self.math = V3Math()

    def scan(self, chain_filter, min_tvl, days_window=7):
        # 1. Obtener todos los pools (API 1)
        raw_pools = self.data.get_all_pools()
        
        # 2. Filtrar básicos (Chain y TVL)
        candidates = []
        for p in raw_pools:
            if p.get('ChainId') == chain_filter:
                try:
                    tvl = float(p.get('Liquidity', 0))
                except:
                    tvl = 0
                
                if tvl >= min_tvl:
                    candidates.append(p)
        
        # Cortamos a los 20 con más volumen para no saturar la API
        candidates = sorted(candidates, key=lambda x: float(x.get('Volume', 0)), reverse=True)[:20]
        
        results = []
        samples_needed = days_window * 3
        
        # 3. Análisis Profundo de cada candidato
        for pool in candidates:
            address = pool.get('pairAddress') 
            if not address: address = pool.get('_id') 

            # Obtenemos el objeto completo (con poolName e history)
            pool_detail = self.data.get_pool_history(address)
            history = pool_detail.get('history', [])
            
            recent_data = history[:samples_needed] if history else []
            if not recent_data: continue

            # --- A. APR Promedio ---
            aprs = [x.get('apr', 0) for x in recent_data if x.get('apr') is not None]
            if aprs:
                # API devuelve APR como número entero/flotante (ej: 50.5 significa 50.5%)
                # NO dividimos por 100. Lo mantenemos como 50.5 para que app.py lo pinte directo con %.
                apr_promedio = sum(aprs) / len(aprs)
            else:
                apr_promedio = 0.0

            # --- B. Volatilidad ---
            prices = []
            for x in recent_data:
                p_native = x.get('priceNative')
                p_usd = x.get('priceUsd')
                
                # Prioridad absoluta: Precio Nativo (Ratio entre tokens)
                if p_native is not None and isinstance(p_native, (int, float)) and p_native > 0:
                    prices.append(float(p_native))
                elif p_usd is not None and isinstance(p_usd, (int, float)) and p_usd > 0:
                    prices.append(float(p_usd))
            
            # Volatilidad viene en decimal (0.30). Multiplicamos por 100 para tener 30.0
            vol_real = self.math.calculate_realized_volatility(prices)
            vol_percent = vol_real * 100.0
            
            costo_riesgo_decimal = self.math.calculate_il_risk_cost(vol_real)
            costo_riesgo_percent = costo_riesgo_decimal * 100.0
            
            # --- C. Margen y Veredicto ---
            margen = apr_promedio - costo_riesgo_percent
            
            veredicto = "❌ REKT"
            if margen > 20.0: veredicto = "💎 GEM"
            elif margen > 5.0: veredicto = "✅ OK"
            elif margen > 0.0: veredicto = "⚠️ JUSTO"
            
            # --- D. Datos para la tabla ---
            
            # LÓGICA DE NOMBRE ROBUSTA
            nombre_par = pool_detail.get('poolName')
            
            # Si el nombre viene vacío o es None, lo construimos nosotros
            if not nombre_par: 
                base = pool.get('BaseToken') or '?'
                quote = pool.get('QuoteToken') or '?'
                
                # Intentamos sacar el feeTier. Puede venir en pool (API 1) o pool_detail (API 2)
                try:
                    raw_fee = pool_detail.get('feeTier') or pool.get('feeTier') or 0
                    # Cálculo: 500 / 10000 = 0.05 (%)
                    fee_calc = float(raw_fee) / 10000.0
                    # Usamos :g para quitar ceros no significativos (ej 1.00 -> 1, 0.05 -> 0.05)
                    fee_str = f"{fee_calc:g}%"
                except:
                    fee_str = "?%"
                
                # Construimos el nombre: "TokenA / TokenB 0.05%"
                nombre_par = f"{base} / {quote} {fee_str}"

            dex_id = pool.get('DexId', 'Unknown').capitalize().replace("-v3", "").replace(" v3", "")
            chain_id = pool.get('ChainId', 'Unknown').capitalize()
            
            # Enviamos números en escala 0-100 (ej: 50.5)
            results.append({
                "Par": nombre_par,
                "Red": chain_id,
                "DEX": dex_id,
                "TVL": float(pool.get('Liquidity',0)),
                "APR Media": apr_promedio,
                "Volatilidad": vol_percent,
                "Riesgo IL": costo_riesgo_percent,
                "Margen": margen,
                "Veredicto": veredicto
            })
            
        return pd.DataFrame(results)
