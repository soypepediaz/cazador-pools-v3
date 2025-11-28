from .data_provider import DataProvider
from .math_core import V3Math
import pandas as pd

class MarketScanner:
    def __init__(self):
        self.data = DataProvider()
        self.math = V3Math()

    def _process_pool_data(self, pool_detail, days_window):
        """Lógica interna para procesar los datos de un pool y devolver un diccionario de métricas."""
        history = pool_detail.get('history', [])
        samples_needed = days_window * 3
        
        recent_data = history[:samples_needed] if history else []
        if not recent_data: return None

        # --- APR ---
        aprs = [x.get('apr', 0) for x in recent_data if x.get('apr') is not None]
        if aprs:
            apr_promedio = sum(aprs) / len(aprs) # Ya viene en escala 0-100
        else:
            apr_promedio = 0.0

        # --- Volatilidad ---
        prices = []
        for x in recent_data:
            p_native = x.get('priceNative')
            p_usd = x.get('priceUsd')
            
            if p_native is not None and isinstance(p_native, (int, float)) and p_native > 0:
                prices.append(float(p_native))
            elif p_usd is not None and isinstance(p_usd, (int, float)) and p_usd > 0:
                prices.append(float(p_usd))
        
        vol_real = self.math.calculate_realized_volatility(prices)
        vol_percent = vol_real * 100.0
        
        costo_riesgo_decimal = self.math.calculate_il_risk_cost(vol_real)
        costo_riesgo_percent = costo_riesgo_decimal * 100.0
        
        # --- Margen ---
        margen = apr_promedio - costo_riesgo_percent
        
        veredicto = "❌ REKT"
        if margen > 20.0: veredicto = "💎 GEM"
        elif margen > 5.0: veredicto = "✅ OK"
        elif margen > 0.0: veredicto = "⚠️ JUSTO"
        
        # --- Nombres ---
        nombre_par = pool_detail.get('poolName')
        if not nombre_par: 
            base = pool_detail.get('BaseToken') or '?'
            quote = pool_detail.get('QuoteToken') or '?'
            try:
                raw_fee = pool_detail.get('feeTier') or 0
                fee_calc = float(raw_fee) / 10000.0
                fee_str = f"{fee_calc:g}%"
            except:
                fee_str = "?%"
            nombre_par = f"{base} / {quote} {fee_str}"

        dex_id = str(pool_detail.get('DexId', 'Unknown')).capitalize().replace("-v3", "").replace(" v3", "")
        chain_id = str(pool_detail.get('ChainId', 'Unknown')).capitalize()
        
        # --- TVL (Corrección Robusta) ---
        # 1. Intentamos leer de la carátula
        tvl = float(pool_detail.get('Liquidity', 0) or 0)
        
        # 2. Si es 0, buscamos el primer valor válido en el historial (del más reciente al más antiguo)
        if tvl == 0 and history:
            for snap in history:
                snap_liq = float(snap.get('Liquidity', 0) or 0)
                if snap_liq > 0:
                    tvl = snap_liq
                    break # Encontrado, paramos de buscar

        return {
            "Par": nombre_par,
            "Red": chain_id,
            "DEX": dex_id,
            "TVL": tvl,
            f"APR ({days_window}d)": apr_promedio,
            "Volatilidad": vol_percent,
            "Riesgo IL": costo_riesgo_percent,
            "Margen": margen,
            "Veredicto": veredicto
        }

    def analyze_single_pool(self, address, days_window=7):
        """Analiza un pool específico dada su dirección (0x...)."""
        # Obtenemos detalle directo de la API 2
        pool_detail = self.data.get_pool_history(address)
        
        if not pool_detail:
            return pd.DataFrame()
            
        result = self._process_pool_data(pool_detail, days_window)
        
        if result:
            result['Address'] = address # Aseguramos que la dirección esté presente
            return pd.DataFrame([result])
        
        return pd.DataFrame()

    def scan(self, chain_filter, min_tvl, days_window=7):
        """Escanea múltiples pools aplicando filtros."""
        raw_pools = self.data.get_all_pools()
        
        candidates = []
        for p in raw_pools:
            if p.get('ChainId') == chain_filter:
                try:
                    tvl = float(p.get('Liquidity', 0))
                except:
                    tvl = 0
                
                if tvl >= min_tvl:
                    candidates.append(p)
        
        candidates = sorted(candidates, key=lambda x: float(x.get('Volume', 0)), reverse=True)[:20]
        
        results = []
        for pool in candidates:
            address = pool.get('pairAddress') 
            if not address: address = pool.get('_id') 

            pool_detail = self.data.get_pool_history(address)
            
            result = self._process_pool_data(pool_detail, days_window)
            if result:
                result['Address'] = address
                results.append(result)
            
        return pd.DataFrame(results)
