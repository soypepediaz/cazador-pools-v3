from .data_provider import DataProvider
from .math_core import V3Math
import pandas as pd

class MarketScanner:
    def __init__(self):
        self.data = DataProvider()
        self.math = V3Math()

    def scan(self, chain_filter, min_tvl):
        # 1. Obtener todos los pools
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
        
        # Si hay demasiados, cortamos a los 20 con más volumen para no saturar la API histórica
        candidates = sorted(candidates, key=lambda x: float(x.get('Volume', 0)), reverse=True)[:20]
        
        results = []
        
        # 3. Análisis Profundo de cada candidato
        for pool in candidates:
            # Obtener dirección para consultar historia
            address = pool.get('pairAddress') 
            if not address: 
                address = pool.get('_id') # Fallback por si la API cambia de nombre
            
            # Descargar historia
            history = self.data.get_pool_history(address)
            
            # --- CORRECCIÓN DE LÓGICA DE VOLATILIDAD ---
            # El riesgo de Impermanent Loss depende de cómo cambia el precio relativo (A vs B),
            # no de cómo cambia el precio en Dólares.
            # Usamos 'priceNative'. Si no existe, usamos 'priceUsd' como emergencia.
            
            prices = []
            if history:
                # Tomamos los últimos 30 datos disponibles
                for x in history[:30]:
                    p_native = x.get('priceNative')
                    p_usd = x.get('priceUsd')
                    
                    # Prioridad: Precio Nativo (Relativo)
                    if p_native is not None and isinstance(p_native, (int, float)) and p_native > 0:
                        prices.append(float(p_native))
                    # Fallback: Precio USD (Solo si no hay nativo)
                    elif p_usd is not None and isinstance(p_usd, (int, float)) and p_usd > 0:
                        prices.append(float(p_usd))
            
            # Calcular Volatilidad Real (HV)
            vol_real = self.math.calculate_realized_volatility(prices)
            
            # Calcular Costo Teórico del Riesgo (LVR)
            costo_riesgo = self.math.calculate_il_risk_cost(vol_real)
            
            # APR Actual (reportado por la API)
            try:
                apr_reportado = float(pool.get('apr', 0)) / 100.0
            except:
                apr_reportado = 0.0
            
            # Margen = Lo que ganas - Lo que te cuesta el riesgo
            margen = apr_reportado - costo_riesgo
            
            # Veredicto (Emoji System)
            veredicto = "❌ REKT"
            if margen > 0.20: veredicto = "💎 GEM"     # Margen excelente (>20%)
            elif margen > 0.05: veredicto = "✅ OK"    # Margen bueno (>5%)
            elif margen > 0: veredicto = "⚠️ JUSTO"    # Margen positivo pero ajustado
            
            # Formatear nombre del par
            base = pool.get('BaseToken', '?')
            quote = pool.get('QuoteToken', '?')
            
            results.append({
                "Par": f"{base}-{quote}",
                "TVL": f"${float(pool.get('Liquidity',0)):,.0f}",
                "APR": f"{apr_reportado*100:.1f}%",
                "Volatilidad (Real)": f"{vol_real*100:.1f}%",
                "Costo Riesgo": f"{costo_riesgo*100:.1f}%",
                "Margen": f"{margen*100:.1f}%",
                "Veredicto": veredicto
            })
            
        return pd.DataFrame(results)
