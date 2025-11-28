from .data_provider import DataProvider
from .math_core import V3Math
import pandas as pd
import math

class MarketScanner:
    def __init__(self):
        self.data = DataProvider()
        self.math = V3Math()

    def _calculate_probability_in_range(self, sd_multiplier):
        """
        Calcula la probabilidad teórica de que el precio se mantenga dentro
        de un rango definido por 'sd_multiplier' desviaciones estándar.
        Asume distribución normal.
        """
        # La función erf devuelve la probabilidad para un rango [-x, x]
        # Para una normal estándar, prob = erf(k / sqrt(2))
        return math.erf(sd_multiplier / math.sqrt(2))

    def _process_pool_data(self, pool_detail, days_window, sd_multiplier=1.0):
        """Procesa datos de un pool y devuelve métricas clave."""
        history = pool_detail.get('history', [])
        
        # Necesitamos datos suficientes para calcular volatilidad
        # Usamos un buffer de seguridad
        min_history_days = max(days_window, 30)
        recent_data = history[:min_history_days * 3] if history else []
        
        if not recent_data: return None

        # --- 1. APR Promedio (Base del API, ventana seleccionada) ---
        # Para el APR usamos solo la ventana seleccionada por el usuario (más reactivo)
        data_window = history[:days_window * 3]
        aprs = [x.get('apr', 0) for x in data_window if x.get('apr') is not None]
        
        if aprs:
            # API devuelve 50.5 para 50.5%. Pasamos a decimal 0.505
            apr_promedio_anual = sum(aprs) / len(aprs) / 100.0 
        else:
            apr_promedio_anual = 0.0

        # --- 2. Volatilidad (Anualizada) ---
        prices = []
        for x in recent_data:
            p_native = x.get('priceNative')
            p_usd = x.get('priceUsd')
            if p_native is not None and isinstance(p_native, (int, float)) and p_native > 0:
                prices.append(float(p_native))
            elif p_usd is not None and isinstance(p_usd, (int, float)) and p_usd > 0:
                prices.append(float(p_usd))
        
        vol_annual = self.math.calculate_realized_volatility(prices)
        
        # --- 3. Rango y Probabilidad ---
        # Escalamos volatilidad al periodo de análisis
        time_scaling = math.sqrt(days_window / 365.0)
        
        # Ancho del rango (hacia un lado)
        range_width_pct = vol_annual * time_scaling * sd_multiplier
        range_width_pct = max(0.005, min(range_width_pct, 2.0)) # Safety caps (0.5% a 200%)

        # Probabilidad estadística de mantenerse en rango (ej: 1SD = 0.68)
        prob_in_range = self._calculate_probability_in_range(sd_multiplier)

        # --- 4. Proyección: Fees Probables vs IL ---
        
        # A. Fees Totales Teóricas (Si precio nunca sale)
        total_yield_theoretical = apr_promedio_anual * (days_window / 365.0)
        
        # B. Fees Probables (Ajustadas por riesgo de salida)
        # Asumimos que ganamos fees proporcionalmente a la probabilidad de estar en rango
        probable_yield = total_yield_theoretical * prob_in_range
        
        # C. Costo IL si tocamos el límite (Riesgo de Ruptura)
        # Usamos la función EXACTA de V3 de math_core
        il_loss_at_limit = self.math.calculate_v3_il_at_limit(range_width_pct)
        
        # --- 5. Veredicto (Esperanza Matemática) ---
        # Margen = Ganancia Probable - Pérdida por IL (en el escenario de ruptura)
        margen = probable_yield - il_loss_at_limit
        
        veredicto = "❌ REKT"
        # Ajustamos umbrales: Si gano más de lo que arriesgo al salir, es bueno.
        if margen > 0.005: veredicto = "💎 GEM"     # Gana > 0.5% neto en el periodo (ajustado prob)
        elif margen > 0.0: veredicto = "✅ OK"      # Gana algo neto
        elif margen > -0.01: veredicto = "⚠️ JUSTO" # Pierde menos del 1%
        
        # --- 6. Datos Básicos ---
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
        
        # TVL Fallback
        tvl = float(pool_detail.get('Liquidity', 0) or 0)
        if tvl == 0 and history:
            for snap in history:
                snap_liq = float(snap.get('Liquidity', 0) or 0)
                if snap_liq > 0:
                    tvl = snap_liq
                    break

        return {
            "Par": nombre_par,
            "Red": chain_id,
            "DEX": dex_id,
            "TVL": tvl,
            f"APR ({days_window}d)": apr_promedio_anual,
            "Volatilidad": vol_annual * 100.0,
            "Rango Est.": range_width_pct * 100.0,
            "Prob. Rango": prob_in_range * 100.0,  # Dato útil para ver
            "Est. Fees": probable_yield * 100.0,   # Yield ajustado por prob.
            "Max IL": il_loss_at_limit * 100.0,
            "Veredicto": veredicto,
            "Margen": margen * 100.0
        }

    def analyze_single_pool(self, address, days_window=7, sd_multiplier=1.0):
        pool_detail = self.data.get_pool_history(address)
        if not pool_detail: return pd.DataFrame()
        
        result = self._process_pool_data(pool_detail, days_window, sd_multiplier)
        if result:
            result['Address'] = address
            return pd.DataFrame([result])
        return pd.DataFrame()

    def scan(self, chain_filter, min_tvl, days_window=7, sd_multiplier=1.0):
        raw_pools = self.data.get_all_pools()
        candidates = []
        for p in raw_pools:
            if p.get('ChainId') == chain_filter:
                try: tvl = float(p.get('Liquidity', 0))
                except: tvl = 0
                if tvl >= min_tvl: candidates.append(p)
        
        candidates = sorted(candidates, key=lambda x: float(x.get('Volume', 0)), reverse=True)[:20]
        
        results = []
        for pool in candidates:
            address = pool.get('pairAddress') 
            if not address: address = pool.get('_id') 

            pool_detail = self.data.get_pool_history(address)
            result = self._process_pool_data(pool_detail, days_window, sd_multiplier)
            if result:
                result['Address'] = address
                results.append(result)
            
        return pd.DataFrame(results)
