from .data_provider import DataProvider
from .math_core import V3Math
import pandas as pd
import math

class MarketScanner:
    def __init__(self):
        self.data = DataProvider()
        self.math = V3Math()

    def _process_pool_data(self, pool_detail, days_window, sd_multiplier=1.0):
        """Lógica interna para procesar los datos de un pool con la nueva estrategia de veredicto."""
        history = pool_detail.get('history', [])
        samples_needed = days_window * 3
        
        recent_data = history[:samples_needed] if history else []
        if not recent_data: return None

        # --- 1. Calcular APR Promedio (Base) ---
        aprs = [x.get('apr', 0) for x in recent_data if x.get('apr') is not None]
        if aprs:
            apr_promedio_anual = sum(aprs) / len(aprs) / 100.0 # Decimal (0.50 para 50%)
        else:
            apr_promedio_anual = 0.0

        # --- 2. Calcular Volatilidad Real ---
        prices = []
        for x in recent_data:
            p_native = x.get('priceNative')
            p_usd = x.get('priceUsd')
            
            if p_native is not None and isinstance(p_native, (int, float)) and p_native > 0:
                prices.append(float(p_native))
            elif p_usd is not None and isinstance(p_usd, (int, float)) and p_usd > 0:
                prices.append(float(p_usd))
        
        vol_annual = self.math.calculate_realized_volatility(prices)
        
        # --- 3. Definir Rango (Bandas de Bollinger) ---
        # Escalamos la volatilidad al periodo de análisis (ej: 7 días)
        # Queremos saber si el APR de 7 días cubre el riesgo de salir del rango de 7 días.
        time_scaling = math.sqrt(days_window / 365.0)
        range_width_pct = vol_annual * time_scaling * sd_multiplier
        range_width_pct = max(0.01, min(range_width_pct, 1.0)) # Safety caps

        # --- 4. Proyección: Fees vs IL ---
        
        # A. Fees Esperadas en el periodo (Si nos mantenemos en rango)
        # Usamos APR Base (Conservador)
        period_yield = apr_promedio_anual * (days_window / 365.0)
        
        # B. Costo IL si tocamos el límite (Exit Risk)
        # ¿Cuánto perdemos vs HODL si el precio se va justo al borde del rango definido?
        il_loss_at_limit = self.math.calculate_v3_il_at_limit(range_width_pct)
        
        # --- 5. Veredicto ---
        # Margen = Lo que gano (Fees) - Lo que pierdo si sale mal (IL)
        margen = period_yield - il_loss_at_limit
        
        veredicto = "❌ REKT"
        # Umbrales ajustados para periodos cortos
        if margen > 0.01: veredicto = "💎 GEM"      # Gana >1% neto en el periodo
        elif margen > 0.0: veredicto = "✅ OK"      # Gana algo positivo
        elif margen > -0.005: veredicto = "⚠️ JUSTO" # Pierde poco (<0.5%)
        
        # Formatos porcentuales para display
        vol_percent = vol_annual * 100.0
        
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
        
        # --- TVL Fallback ---
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
            "Volatilidad": vol_percent,
            "Rango Est.": range_width_pct * 100.0,  # Nuevo dato visual
            "Est. Fees": period_yield * 100.0,      # Nuevo dato visual
            "Max IL": il_loss_at_limit * 100.0,     # Nuevo dato visual
            "Veredicto": veredicto,
            "Margen": margen * 100.0                # Para ordenar
        }

    def analyze_single_pool(self, address, days_window=7, sd_multiplier=1.0):
        """Analiza un pool específico dada su dirección (0x...)."""
        pool_detail = self.data.get_pool_history(address)
        if not pool_detail: return pd.DataFrame()
        
        result = self._process_pool_data(pool_detail, days_window, sd_multiplier)
        if result:
            result['Address'] = address
            return pd.DataFrame([result])
        return pd.DataFrame()

    def scan(self, chain_filter, min_tvl, days_window=7, sd_multiplier=1.0):
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
            
            result = self._process_pool_data(pool_detail, days_window, sd_multiplier)
            if result:
                result['Address'] = address
                results.append(result)
            
        return pd.DataFrame(results)
