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
        
        amount_x_unit = 0
        amount_y_unit = 0
        
        if p_native <= lower:
            amount_x_unit = (sqrt_b - sqrt_a) / (sqrt_a * sqrt_b)
        elif p_native >= upper:
            amount_y_unit = sqrt_b - sqrt_a
        else:
            amount_x_unit = (sqrt_b - sqrt_p) / (sqrt_p * sqrt_b)
            amount_y_unit = sqrt_p - sqrt_a
            
        cost_unit_usd = (amount_x_unit * p_base_usd) + (amount_y_unit * p_quote_usd)
        
        if cost_unit_usd == 0: return 0, 0, 0
        
        L = principal_usd / cost_unit_usd
        
        return L, amount_x_unit * L, amount_y_unit * L

    def _calculate_dynamic_range(self, full_data, current_idx, vol_days, sd_multiplier):
        """
        Calcula el ancho del rango basándose en la volatilidad de los 'vol_days' previos al 'current_idx'.
        """
        samples_needed = vol_days * 3
        start_idx = max(0, current_idx - samples_needed)
        
        # Extraemos los precios de la ventana de volatilidad
        recent_window = full_data[start_idx : current_idx]
        prices = [x.get('priceNative') or x.get('priceUsd') for x in recent_window]
        
        # Calculamos volatilidad anualizada de esa ventana
        vol_annual = self.math.calculate_realized_volatility(prices)
        
        # Escalamos al periodo de la ventana para definir el ancho
        # (Asumimos que queremos cubrir movimientos esperados en un horizonte similar al de la vol)
        # Nota: Normalmente el rango se ajusta para X días futuros, aquí usamos vol_days como proxy de horizonte
        time_scaling = math.sqrt(vol_days / 365.0)
        
        range_width_pct = vol_annual * time_scaling * sd_multiplier
        
        # Límites de seguridad (Min 1%, Max 100%)
        return max(0.01, min(range_width_pct, 1.0)), vol_annual

    def run_simulation(self, history, investment_usd, sd_multiplier, sim_days=30, vol_days=7, fee_tier=0.003, auto_rebalance=False):
        """
        sim_days: Días a simular (Backtest duration).
        vol_days: Ventana de días para calcular la volatilidad (Lookback window).
        """
        if not history: return None
        
        # 1. Preparar Datos Cronológicos
        # Necesitamos datos para la simulación + un buffer previo para la volatilidad inicial
        total_samples = (sim_days + vol_days) * 3
        
        # history viene (Nuevo -> Viejo), invertimos a (Viejo -> Nuevo)
        full_history_chrono = history[:total_samples][::-1]
        
        # Validar si hay suficientes datos para arrancar
        min_warmup_samples = vol_days * 3
        if len(full_history_chrono) < min_warmup_samples + 3: # +3 para tener algo que simular
            return None

        # Definimos dónde empieza la simulación real dentro de full_history_chrono
        # Debe haber al menos 'min_warmup_samples' antes del start_idx
        sim_start_idx = max(min_warmup_samples, len(full_history_chrono) - (sim_days * 3))
        
        # --- 2. Inicialización (En el momento T = Start Simulation) ---
        start_point = full_history_chrono[sim_start_idx]
        
        p_base_usd_0 = start_point.get('priceUsd', 0)
        p_native_0 = start_point.get('priceNative') or start_point.get('priceUsd', 0)
        
        if not p_base_usd_0 or not p_native_0: return None

        # A. Calcular Rango Inicial con los datos PREVIOS al inicio
        range_width_pct, initial_vol = self._calculate_dynamic_range(full_history_chrono, sim_start_idx, vol_days, sd_multiplier)
        
        lower_price = p_native_0 * (1 - range_width_pct)
        upper_price = p_native_0 * (1 + range_width_pct)
        
        # B. Comprar Liquidez Inicial
        liquidity, hodl_x, hodl_y = self._calculate_liquidity_and_amounts(
            investment_usd, p_native_0, p_base_usd_0, lower_price, upper_price
        )
        
        current_principal_usd = investment_usd
        accumulated_fees_usd = 0.0
        rebalance_count = 0
        
        results = []
        
        # --- 3. Bucle de Simulación (Desde start_idx hasta el final) ---
        # Iteramos sobre los datos de simulación, pero mantenemos acceso a 'full_history_chrono' por índice
        # para poder mirar atrás si necesitamos rebalancear.
        
        for i in range(sim_start_idx, len(full_history_chrono)):
            snap = full_history_chrono[i]
            
            p_native_t = snap.get('priceNative') or snap.get('priceUsd', 0)
            p_base_usd_t = snap.get('priceUsd', 0)
            
            if p_native_t == 0 or p_base_usd_t == 0: continue
            
            p_quote_usd_t = p_base_usd_t / p_native_t
            
            # --- A. Lógica de Rebalanceo Dinámico ---
            in_range = lower_price <= p_native_t <= upper_price
            
            if auto_rebalance and not in_range:
                # 1. Valor residual (Mark-to-Market de salida)
                ax, ay = self.math.calculate_amounts(liquidity, math.sqrt(p_native_t), math.sqrt(lower_price), math.sqrt(upper_price))
                curr_val_usd = (ax * p_base_usd_t) + (ay * p_quote_usd_t)
                
                # 2. Penalización Swap
                current_principal_usd = curr_val_usd * 0.997
                
                # 3. Recalcular Rango Dinámico (Usando la volatilidad de los últimos vol_days)
                # Miramos atrás desde el índice actual 'i'
                new_width_pct, _ = self._calculate_dynamic_range(full_history_chrono, i, vol_days, sd_multiplier)
                
                lower_price = p_native_t * (1 - new_width_pct)
                upper_price = p_native_t * (1 + new_width_pct)
                
                # 4. Recomprar Liquidez
                liquidity, _, _ = self._calculate_liquidity_and_amounts(
                    current_principal_usd, p_native_t, p_base_usd_t, lower_price, upper_price
                )
                rebalance_count += 1
                in_range = True
            
            # --- B. Valoración ---
            curr_x, curr_y = self.math.calculate_amounts(
                liquidity, math.sqrt(p_native_t), math.sqrt(lower_price), math.sqrt(upper_price)
            )
            val_pos_usd = (curr_x * p_base_usd_t) + (curr_y * p_quote_usd_t)
            
            # --- C. Fees ---
            apr_snapshot = snap.get('apr', 0)
            fees_earned_period = 0.0
            
            if in_range and apr_snapshot:
                # APR directo del API / 1095 periodos
                base_period_yield = (float(apr_snapshot) / 100.0) / (365.0 * 3.0)
                fees_earned_period = val_pos_usd * base_period_yield
                accumulated_fees_usd += fees_earned_period
            
            # --- D. HODL ---
            val_hodl_now = (hodl_x * p_base_usd_t) + (hodl_y * p_quote_usd_t)
            
            results.append({
                "Date": self._parse_date(snap.get('date')),
                "Price": p_native_t,
                "Range Min": lower_price,
                "Range Max": upper_price,
                "In Range": in_range,
                "APR Period": float(apr_snapshot) if apr_snapshot else 0.0,
                "Fees Period": fees_earned_period,
                "Fees Acum": accumulated_fees_usd,
                "Valor Principal": val_pos_usd,
                "Valor Total": val_pos_usd + accumulated_fees_usd,
                "HODL Value": val_hodl_now
            })
            
        metadata = {
            "initial_volatility": initial_vol,
            "rebalances": rebalance_count
        }
            
        return pd.DataFrame(results), lower_price, upper_price, metadata
