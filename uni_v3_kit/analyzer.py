from .data_provider import DataProvider
from .math_core import V3Math
import pandas as pd

class MarketScanner:
    def __init__(self):
        self.data = DataProvider()
        self.math = V3Math()

    def scan(self, chain_filter, min_tvl, days_window=7):
        """
        days_window: Número de días para calcular la media móvil (7, 14, 30).
        """
        # 1. Obtener todos los pools
        raw_pools = self.data.get_all_pools()
        
        # 2. Filtrar básicos (Chain y TVL)
        candidates = []
        for p in raw_pools:
            # Filtro de Cadena (Si chain_filter es "all", pasamos todo, si no, filtramos)
            # Nota: Para tu app actual usas un selectbox fijo, así que filtramos normal.
            if p.get('ChainId') == chain_filter:
                try:
                    tvl = float(p.get('Liquidity', 0))
                except:
                    tvl = 0
                
                if tvl >= min_tvl:
                    candidates.append(p)
        
        # Si hay demasiados, cortamos a los 20 con más volumen para no saturar
        candidates = sorted(candidates, key=lambda x: float(x.get('Volume', 0)), reverse=True)[:20]
        
        results = []
        
        # Calculamos cuántos datos necesitamos del historial
        # La API guarda aprox 3 datos por día (cada 8h).
        samples_needed = days_window * 3
        
        # 3. Análisis Profundo de cada candidato
        for pool in candidates:
            address = pool.get('pairAddress') 
            if not address: address = pool.get('_id') 

            # Descargar historia
            history = self.data.get_pool_history(address)
            
            # --- CORTE DE TIEMPO (MEDIA MÓVIL) ---
            # La API devuelve los datos ordenados del más nuevo al más viejo.
            # Tomamos solo los necesarios para la ventana de tiempo seleccionada.
            recent_data = history[:samples_needed] if history else []
            
            if not recent_data:
                continue # Si no hay historia, saltamos

            # A. Calcular APR Promedio (SMA)
            aprs = [x.get('apr', 0) for x in recent_data if x.get('apr') is not None]
            if aprs:
                apr_promedio = sum(aprs) / len(aprs) / 100.0 # Pasamos a decimal
            else:
                apr_promedio = 0.0

            # B. Calcular Volatilidad (Usando priceNative) en el mismo periodo
            prices = []
            for x in recent_data:
                p_native = x.get('priceNative')
                p_usd = x.get('priceUsd')
                
                # Prioridad: Precio Nativo
                if p_native is not None and isinstance(p_native, (int, float)) and p_native > 0:
                    prices.append(float(p_native))
                elif p_usd is not None and isinstance(p_usd, (int, float)) and p_usd > 0:
                    prices.append(float(p_usd))
            
            vol_real = self.math.calculate_realized_volatility(prices)
            costo_riesgo = self.math.calculate_il_risk_cost(vol_real)
            
            # C. Margen y Veredicto
            margen = apr_promedio - costo_riesgo
            
            veredicto = "❌ REKT"
            if margen > 0.20: veredicto = "💎 GEM"
            elif margen > 0.05: veredicto = "✅ OK"
            elif margen > 0: veredicto = "⚠️ JUSTO"
            
            # D. Datos Extra para la Tabla
            # Formatear Fee Tier (Ej: 3000 -> 0.3%, 100 -> 0.01%)
            try:
                fee_raw = float(pool.get('feeTier', 0))
                # La convención suele ser 10000 = 100%? No, en Uniswap v3:
                # 3000 = 0.3%, 500 = 0.05%, 10000 = 1%. 
                # Por tanto dividimos por 10000 para tener decimal absoluto, o por 100 para porcentaje visual.
                fee_formatted = f"{fee_raw / 10000:.2%}" # Esto muestra 0.30%
            except:
                fee_formatted = "?"

            dex_id = pool.get('DexId', 'Unknown').capitalize()
            chain_id = pool.get('ChainId', 'Unknown').capitalize()
            
            # E. Construir fila
            base = pool.get('BaseToken', '?')
            quote = pool.get('QuoteToken', '?')

            results.append({
                "Par": f"{base}-{quote}",
                "Red": chain_id,
                "Protocolo": dex_id,
                "Fee": fee_formatted,
                "TVL": f"${float(pool.get('Liquidity',0)):,.0f}",
                f"APR ({days_window}d)": f"{apr_promedio*100:.1f}%", # Header dinámico
                f"Volatilidad": f"{vol_real*100:.1f}%",
                "Costo Riesgo": f"{costo_riesgo*100:.1f}%",
                "Margen": f"{margen*100:.1f}%",
                "Veredicto": veredicto
            })
            
        return pd.DataFrame(results)
