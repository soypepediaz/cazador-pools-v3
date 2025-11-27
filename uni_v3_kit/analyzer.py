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
        
        # 2. Filtrar básicos
        candidates = []
        for p in raw_pools:
            if p.get('ChainId') == chain_filter:
                tvl = float(p.get('Liquidity', 0))
                if tvl >= min_tvl:
                    candidates.append(p)
        
        # Si hay demasiados, cortamos a los 20 con más volumen para no saturar
        candidates = sorted(candidates, key=lambda x: float(x.get('Volume', 0)), reverse=True)[:15]
        
        results = []
        
        # 3. Análisis Profundo de cada candidato
        for pool in candidates:
            address = pool.get('pairAddress') # Ojo, la API usa keys distintas a veces
            if not address: address = pool.get('_id') # Fallback

            # Descargar historia
            history = self.data.get_pool_history(address)
            
            # Extraer precios últimos 30 días
            prices = [x['priceUsd'] for x in history[:30] if x.get('priceUsd')]
            
            # Calcular Volatilidad Real
            vol_real = self.math.calculate_realized_volatility(prices)
            costo_riesgo = self.math.calculate_il_risk_cost(vol_real)
            
            # APR Actual (reportado)
            apr_reportado = float(pool.get('apr', 0)) / 100.0
            
            # Margen
            margen = apr_reportado - costo_riesgo
            
            veredicto = "❌ REKT"
            if margen > 0.20: veredicto = "💎 GEM"
            elif margen > 0.05: veredicto = "✅ OK"
            elif margen > 0: veredicto = "⚠️ JUSTO"
            
            results.append({
                "Par": f"{pool.get('BaseToken')}-{pool.get('QuoteToken')}",
                "TVL": f"${float(pool.get('Liquidity',0)):,.0f}",
                "APR": f"{apr_reportado*100:.1f}%",
                "Volatilidad (Real)": f"{vol_real*100:.1f}%",
                "Costo Riesgo": f"{costo_riesgo*100:.1f}%",
                "Margen": f"{margen*100:.1f}%",
                "Veredicto": veredicto
            })
            
        return pd.DataFrame(results)
