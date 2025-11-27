import pandas as pd
import math
from datetime import datetime
from .math_core import V3Math

class Backtester:
    def __init__(self):
        self.math = V3Math()

    def _parse_date(self, date_val):
        try:
            return datetime.strptime(str(date_val), "%Y%m%d%H%M%S")
        except:
            return date_val

    def _calculate_liquidity_and_amounts(self, principal_usd, p_native, p_base_usd, lower, upper):
        """Helper para calcular L y tokens iniciales dado un capital en USD"""
        if p_native <= 0 or p_base_usd <= 0: return 0, 0, 0
        
        p_quote_usd = p_base_usd / p_native
        
        sqrt_p = math.sqrt(p_native)
        sqrt_a = math.sqrt(lower)
        sqrt_b = math.sqrt(upper)
        
        # Cantidades teóricas para L=1
        amount_x_unit = 0
        amount_y_unit = 0
        
        if p_native <= lower:
            amount_x_unit = (sqrt_b - sqrt_a) / (sqrt_a * sqrt_b)
        elif p_native >= upper:
            amount_y_unit = sqrt_b - sqrt_a
        else:
            amount_x_unit = (sqrt_b - sqrt_p) / (sqrt_p * sqrt_b)
            amount_y_unit = sqrt_p - sqrt_a
            
        # Costo de esa unidad de L
        cost_unit_usd = (amount_x_unit * p_base_usd) + (amount_y_unit * p_quote_usd)
        
        if cost_unit_usd == 0: return 0, 0, 0
        
        L = principal_usd / cost_unit_usd
        
        return L, amount_x_unit * L, amount_y_unit * L

    def run_simulation(self, history, investment_usd, sd_multiplier, days=30, fee_tier=0.003, auto_rebalance=False):
        if not history: return None
        
        sim_data = history[:days*3][::-1] 
        if not sim_data: return None

        # --- 1. Cálculo de Volatilidad y Rango ---
        # Extraemos precios para calcular volatilidad real del periodo
        prices_native = [x.get('priceNative') or x.get('priceUsd') for x in sim_data]
        vol_annual = self.math.calculate_realized_volatility(prices_native)
        
        # Ancho del rango basado en SD (Desviación Típica)
        # Escalamos la volatilidad anual al periodo de holding esperado
        time_scaling = math.sqrt(days / 365.0)
        range_width_pct = vol_annual * time_scaling * sd_multiplier
        range_width_pct = max(0.01, min(range_width_pct, 2.0)) # Cap de seguridad (1% a 200%)
        
        # Multiplicador de Eficiencia (Boost de APR por concentración)
        efficiency_mult = self.math.calculate_concentration_multiplier(range_width_pct)

        # --- 2. Inicialización (Día 0) ---
        start_point = sim_data[0]
        p_base_usd_0 = start_point.get('priceUsd', 0)
        p_native_0 = start_point.get('priceNative') or start_point.get('priceUsd', 0)
        
        if not p_base_usd_0 or not p_native_0: return None

        # Límites iniciales
        lower_price = p_native_0 * (1 - range_width_pct)
        upper_price = p_native_0 * (1 + range_width_pct)
        
        # Calculamos Liquidez Inicial y Tokens para HODL
        liquidity, hodl_x, hodl_y = self._calculate_liquidity_and_amounts(
            investment_usd, p_native_0, p_base_usd_0, lower_price, upper_price
        )
        
        # Variables de estado
        current_principal_usd = investment_usd
        accumulated_fees_usd = 0.0
        rebalance_count = 0
        
        results = []
        
        # --- 3. Bucle de Simulación ---
        for snap in sim_data:
            p_native_t = snap.get('priceNative') or snap.get('priceUsd', 0)
            p_base_usd_t = snap.get('priceUsd', 0)
            
            if p_native_t == 0 or p_base_usd_t == 0: continue
            
            p_quote_usd_t = p_base_usd_t / p_native_t
            
            # --- A. Lógica de Rebalanceo ---
            in_range = lower_price <= p_native_t <= upper_price
            
            if auto_rebalance and not in_range:
                # 1. Calcular valor residual de la posición actual (Mark-to-Market antes de cerrar)
                # Como estamos fuera de rango, tenemos 100% de un solo token
                curr_val_usd = 0
                if p_native_t < lower_price:
                    # Todo en Base (X)
                    amount_x = self.math.calculate_amounts(liquidity, math.sqrt(lower_price), math.sqrt(lower_price), math.sqrt(upper_price))[0]
                    # Nota: Usamos sqrt(lower) porque el precio real está más abajo, pero la liquidez V3 se quedó allí
                    # Corrección: En V3, si P < Lower, tienes cantidad fija de X.
                    # Usamos la función math_core para obtener esa cantidad exacta.
                    ax, ay = self.math.calculate_amounts(liquidity, math.sqrt(p_native_t), math.sqrt(lower_price), math.sqrt(upper_price))
                    curr_val_usd = ax * p_base_usd_t
                else:
                    # Todo en Quote (Y)
                    ax, ay = self.math.calculate_amounts(liquidity, math.sqrt(p_native_t), math.sqrt(lower_price), math.sqrt(upper_price))
                    curr_val_usd = ay * p_quote_usd_t
                
                # 2. Aplicar coste de Swap/Gas (0.3% del principal)
                current_principal_usd = curr_val_usd * 0.997
                
                # 3. Recentrar Rango
                lower_price = p_native_t * (1 - range_width_pct)
                upper_price = p_native_t * (1 + range_width_pct)
                
                # 4. Recalcular Liquidez (L) con el nuevo dinero y nuevo rango
                liquidity, _, _ = self._calculate_liquidity_and_amounts(
                    current_principal_usd, p_native_t, p_base_usd_t, lower_price, upper_price
                )
                
                rebalance_count += 1
                in_range = True # Ahora estamos dentro
            
            # --- B. Valoración Mark-to-Market ---
            # Cuántos tokens tengo AHORA en el pool
            curr_x, curr_y = self.math.calculate_amounts(
                liquidity, math.sqrt(p_native_t), math.sqrt(lower_price), math.sqrt(upper_price)
            )
            
            val_pos_usd = (curr_x * p_base_usd_t) + (curr_y * p_quote_usd_t)
            
            # --- C. Fees (Con Boost de Eficiencia) ---
            apr_snapshot = snap.get('apr', 0)
            if in_range and apr_snapshot:
                # APR Base / Periodos
                base_yield = (float(apr_snapshot) / 100.0) / (365.0 * 3.0)
                # APR Real = Base * Eficiencia
                real_yield = base_yield * efficiency_mult
                
                fees_earned = val_pos_usd * real_yield
                accumulated_fees_usd += fees_earned
            
            # --- D. HODL Benchmark (Tokens fijos día 0) ---
            val_hodl_now = (hodl_x * p_base_usd_t) + (hodl_y * p_quote_usd_t)
            
            results.append({
                "Date": self._parse_date(snap.get('date')),
                "Price": p_native_t,
                "Range Min": lower_price,
                "Range Max": upper_price,
                "In Range": in_range,
                "Fees Acum": accumulated_fees_usd,
                "Valor Principal": val_pos_usd,
                "Valor Total": val_pos_usd + accumulated_fees_usd,
                "HODL Value": val_hodl_now
            })
            
        metadata = {
            "volatility": vol_annual,
            "range_width_pct": range_width_pct,
            "efficiency": efficiency_mult,
            "rebalances": rebalance_count
        }
            
        return pd.DataFrame(results), lower_price, upper_price, metadata
