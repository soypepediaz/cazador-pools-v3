from .data_provider import DataProvider
from .math_core import V3Math
import pandas as pd

class MarketScanner:
    def __init__(self):
        self.data = DataProvider()
        self.math = V3Math()

    def scan(self, chain_filter, min_tvl, days_window=7):
        """
        Escanea el mercado aplicando filtros y calculando métricas históricas.
        """
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
        
        # Ordenamos por volumen y cortamos a los 20 mejores para no saturar la API
        candidates = sorted(candidates, key=lambda x: float(x.get('Volume', 0)), reverse=True)[:20]
        
        results = []
        
        # Calculamos cuántos datos necesitamos del historial (3 snapshots por día aprox)
        samples_needed = days_window * 3
        
        # 3. Análisis Profundo de cada candidato
        for pool in candidates:
            # Identificar ID para la API histórica
            address = pool.get('pairAddress') 
            if not address: address = pool.get('_id') 

            # Descargar detalle completo (API 2)
            pool_detail = self.data.get_pool_history(address)
            history = pool_detail.get('history', [])
            
            # Si no hay historia reciente, saltamos
            recent_data = history[:samples_needed] if history else []
            if not recent_data: continue

            # --- A. APR Promedio (Media Móvil) ---
            aprs = [x.get('apr', 0) for x in recent_data if x.get('apr') is not None]
            
            if aprs:
                # La API devuelve el APR como número entero/flotante (ej: 50.5 significa 50.5%)
                # Calculamos la media
                avg_apr_raw = sum(aprs) / len(aprs)
                # Lo convertimos a decimal (0.505) para que Streamlit lo formatee después
                apr_promedio = avg_apr_raw / 100.0
            else:
                apr_promedio = 0.0

            # --- B. Volatilidad (Usando priceNative) ---
            prices = []
            for x in recent_data:
                p_native = x.get('priceNative')
                p_usd = x.get('priceUsd')
                
                # Prioridad absoluta: Precio Nativo (Ratio entre tokens)
                # Esto evita que pares estables parezcan volátiles si el USD cambia
                if p_native is not None and isinstance(p_native, (int, float)) and p_native > 0:
                    prices.append(float(p_native))
                elif p_usd is not None and isinstance(p_usd, (int, float)) and p_usd > 0:
                    prices.append(float(p_usd))
            
            vol_real = self.math.calculate_realized_volatility(prices)
            costo_riesgo = self.math.calculate_il_risk_cost(vol_real)
            
            # --- C. Margen y Veredicto ---
            margen = apr_promedio - costo_riesgo
            
            veredicto = "❌ REKT"
            if margen > 0.20: veredicto = "💎 GEM"
            elif margen > 0.05: veredicto = "✅ OK"
            elif margen > 0: veredicto = "⚠️ JUSTO"
            
            # --- D. Datos para la tabla (NÚMEROS PUROS) ---
            
            # Recuperamos el nombre oficial del pool desde la API 2
            # Si falla, construimos uno básico con los tickers
            base = pool.get('BaseToken', '?')
            quote = pool.get('QuoteToken', '?')
            nombre_par = pool_detail.get('poolName', f"{base}-{quote}")

            dex_id = pool.get('DexId', 'Unknown').capitalize().replace("-v3", "").replace(" v3", "")
            chain_id = pool.get('ChainId', 'Unknown').capitalize()
            
            # Añadimos la fila. Importante: APR, Vol, Riesgo y Margen van como FLOAT
            # para que la ordenación en la tabla funcione numéricamente.
            results.append({
                "Par": nombre_par,
                "Red": chain_id,
                "Protocolo": dex_id,
                "TVL": float(pool.get('Liquidity',0)),
                f"APR ({days_window}d)": apr_promedio,
                "Volatilidad": vol_real,
                "Costo Riesgo": costo_riesgo,
                "Margen": margen,
                "Veredicto": veredicto
            })
            
        return pd.DataFrame(results)
