from .data_provider import DataProvider
from .math_core import V3Math
import pandas as pd
import math

class MarketScanner:
    def __init__(self):
        self.data = DataProvider()
        self.math = V3Math()

    def _calculate_probability_in_range(self, sd_multiplier):
        """Calcula probabilidad de estar en rango (distribución normal)"""
        return math.erf(sd_multiplier / math.sqrt(2))

    def _process_pool_data(self, pool_detail, days_window, sd_multiplier=1.0):
        """Procesa datos de un pool y devuelve métricas clave."""
        history = pool_detail.get('history', [])
        
        # Mínimo de historia para volatilidad fiable
        min_history_days = max(days_window, 30)
        recent_data = history[:min_history_days * 3] if history else []
        
        if not recent_data: return None

        # --- 1. APR Promedio (Ventana seleccionada) ---
        data_window = history[:days_window * 3]
        aprs = [x.get('apr', 0) for x in data_window if x.get('apr') is not None]
        
        if aprs:
            # API devuelve 50.5 para 50.5%. Pasamos a decimal 0.505
            apr_promedio_anual = sum(aprs) / len(aprs) / 100.0 
        else:
            apr_promedio_anual = 0.0

        # --- 2. Volatilidad ---
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
        time_scaling = math.sqrt(days_window / 365.0)
        range_width_pct = vol_annual * time_scaling * sd_multiplier
        range_width_pct = max(0.005, min(range_width_pct, 2.0))

        prob_in_range = self._calculate_probability_in_range(sd_multiplier)

        # --- 4. Proyección: Fees Probables vs IL ---
        
        # Fees Totales Teóricas
        total_yield_theoretical = apr_promedio_anual * (days_window / 365.0)
        
        # Fees Probables (Ajustadas por probabilidad)
        probable_yield = total_yield_theoretical * prob_in_range
        
        # Costo IL (Riesgo de Ruptura)
        il_loss_at_limit = self.math.calculate_v3_il_at_limit(range_width_pct)
        
        # --- 5. Métricas de Decisión ---
        # Margen Neto
        margen = probable_yield - il_loss_at_limit
        
        # Ratio Beneficio / Riesgo (Nuevo nombre)
        riesgo_safe = max(il_loss_at_limit, 0.0001)
        ratio_br = probable_yield / riesgo_safe
        
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
            # "Prob. Rango": Eliminado por solicitud
            "Est. Fees": probable_yield * 100.0,
            "IL": il_loss_at_limit * 100.0,        # Renombrado de Max IL a IL
            "Ratio F/IL": ratio_br,                # Renombrado de Ratio F/R
            "Margen": margen * 100.0
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

    def scan(self, target_chains, min_tvl, days_window, sd_multiplier, min_apr, selected_assets, custom_asset=None):
        """
        Escanea múltiples pools aplicando filtros avanzados.
        target_chains: Lista de cadenas (ej: ['ethereum', 'arbitrum']) o vacía para todas.
        selected_assets: Lista de activos (ej: ['BTC', 'ETH']).
        custom_asset: Nombre de activo personalizado.
        """
        raw_pools = self.data.get_all_pools()
        candidates = []
        
        # Preparar lista de búsqueda de activos (normalizada a mayúsculas)
        assets_to_search = []
        if selected_assets:
            assets_to_search = [a.upper() for a in selected_assets if a != "Otro"]
        if custom_asset:
            assets_to_search.append(custom_asset.upper())
            
        for p in raw_pools:
            # 1. Filtro Red (Si la lista no está vacía y no contiene 'Todas')
            # Nota: Desde app enviaremos lista vacía si el usuario quiere 'Todas'
            p_chain = p.get('ChainId')
            if target_chains and p_chain not in target_chains:
                continue
                
            # 2. Filtro TVL
            try: tvl = float(p.get('Liquidity', 0))
            except: tvl = 0
            if tvl < min_tvl: continue
            
            # 3. Filtro Activos (Si hay seleccionados)
            if assets_to_search:
                base = str(p.get('BaseToken', '')).upper()
                quote = str(p.get('QuoteToken', '')).upper()
                # Debe contener AL MENOS UNO de los activos buscados
                found = False
                for asset in assets_to_search:
                    if asset in base or asset in quote:
                        found = True
                        break
                if not found: continue

            candidates.append(p)
        
        # Priorizar por Volumen para analizar primero los más líquidos
        # Aumentamos el límite de pre-candidatos para tener margen tras el filtro de APR
        candidates = sorted(candidates, key=lambda x: float(x.get('Volume', 0)), reverse=True)[:150]
        
        results = []
        for pool in candidates:
            address = pool.get('pairAddress') 
            if not address: address = pool.get('_id') 

            pool_detail = self.data.get_pool_history(address)
            
            result = self._process_pool_data(pool_detail, days_window, sd_multiplier)
            
            if result:
                # 4. Filtro APR Mínimo (Sobre el calculado real del periodo analizado)
                # El result tiene el APR en formato decimal 0.50, multiplicamos por 100 para comparar con input usuario (10%)
                apr_calc = result.get(f"APR ({days_window}d)", 0) * 100
                
                if apr_calc >= min_apr:
                    result['Address'] = address
                    results.append(result)
            
        # Convertimos a DataFrame
        df = pd.DataFrame(results)
        
        if not df.empty:
            # Ordenar por TVL descendente y devolver Top 100
            df = df.sort_values(by="TVL", ascending=False).head(100)
            
        return df
