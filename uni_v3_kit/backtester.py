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

    def run_simulation(self, history, investment_usd, range_width_std, days=30, fee_tier=0.003):
        if not history: return None
        
        sim_data = history[:days*3][::-1] 
        if not sim_data: return None

        # --- 1. Inicialización (Día 0) ---
        start_point = sim_data[0]
        
        # Precio del Activo Base en USD (ej. Precio cbBTC en USD)
        p_base_usd_0 = start_point.get('priceUsd', 0)
        
        # Precio Nativo (Relación Base/Quote, ej. cbBTC/SOL)
        p_native_0 = start_point.get('priceNative')
        
        if not p_base_usd_0 or not p_native_0: return None

        # Derivamos el precio del Activo Quote en USD (ej. Precio SOL en USD)
        # Matemáticamente: P_quote_usd = P_base_usd / Ratio_base_quote
        p_quote_usd_0 = p_base_usd_0 / p_native_0

        # Definimos Rango
        lower_price = p_native_0 * (1 - range_width_std)
        upper_price = p_native_0 * (1 + range_width_std)
        
        # --- CÁLCULO DE LIQUIDEZ REAL (L) ---
        # Calculamos cuántos tokens X e Y compramos inicialmente con la inversión
        sqrt_p = math.sqrt(p_native_0)
        sqrt_a = math.sqrt(lower_price)
        sqrt_b = math.sqrt(upper_price)
        
        # Unidades de token por unidad de Liquidez (L=1)
        amount_x_unit = 0 # Base
        amount_y_unit = 0 # Quote
        
        if p_native_0 <= lower_price:
            amount_x_unit = (sqrt_b - sqrt_a) / (sqrt_a * sqrt_b)
        elif p_native_0 >= upper_price:
            amount_y_unit = sqrt_b - sqrt_a
        else:
            amount_x_unit = (sqrt_b - sqrt_p) / (sqrt_p * sqrt_b)
            amount_y_unit = sqrt_p - sqrt_a
            
        # Costo en USD de comprar esa unidad de Liquidez
        cost_unit_l_usd = (amount_x_unit * p_base_usd_0) + (amount_y_unit * p_quote_usd_0)
        
        if cost_unit_l_usd == 0: return None
        
        # Liquidez total que podemos comprar
        liquidity = investment_usd / cost_unit_l_usd
        
        # Tokens iniciales (para comparar con HODL)
        initial_hold_x = amount_x_unit * liquidity
        initial_hold_y = amount_y_unit * liquidity

        results = []
        accumulated_fees_usd = 0.0
        
        # --- 2. Simulación Paso a Paso ---
        for snap in sim_data:
            # Datos actuales
            p_native_t = snap.get('priceNative', 0)
            p_base_usd_t = snap.get('priceUsd', 0)
            
            if p_native_t == 0 or p_base_usd_t == 0: continue
            
            # Precio Quote actual en USD
            p_quote_usd_t = p_base_usd_t / p_native_t
            
            # A. Valor HODL (Si hubiéramos guardado los tokens en la billetera)
            # Simplemente valoramos los tokens iniciales a precios de hoy
            val_hodl_now = (initial_hold_x * p_base_usd_t) + (initial_hold_y * p_quote_usd_t)
            
            # B. Valor Posición V3 (Mark-to-Market)
            # Calculamos qué tokens tenemos DENTRO del pool ahora mismo según el rango
            curr_x = 0
            curr_y = 0
            sqrt_p_t = math.sqrt(p_native_t)
            in_range = lower_price <= p_native_t <= upper_price
            
            if p_native_t <= lower_price:
                # Precio bajó mucho -> Tenemos 100% Base (X)
                curr_x = (sqrt_b - sqrt_a) / (sqrt_a * sqrt_b) * liquidity
            elif p_native_t >= upper_price:
                # Precio subió mucho -> Tenemos 100% Quote (Y)
                curr_y = (sqrt_b - sqrt_a) * liquidity
            else:
                # En rango -> Mezcla
                curr_x = (sqrt_b - sqrt_p_t) / (sqrt_p_t * sqrt_b) * liquidity
                curr_y = (sqrt_p_t - sqrt_a) * liquidity
                
            # Valor actual de los tokens en el pool en USD
            val_pos_usd = (curr_x * p_base_usd_t) + (curr_y * p_quote_usd_t)
            
            # C. Fees
            apr_snapshot = snap.get('apr', 0)
            if in_range and apr_snapshot:
                # El APR se aplica sobre el valor actual de la posición en ese momento
                period_yield = (float(apr_snapshot) / 100.0) / (365.0 * 3.0)
                fees_usd = val_pos_usd * period_yield
                accumulated_fees_usd += fees_usd
            
            formatted_date = self._parse_date(snap.get('date'))
            
            results.append({
                "Date": formatted_date,
                "Price": p_native_t,
                "In Range": in_range,
                "Fees Acum": accumulated_fees_usd,
                "Valor Principal": val_pos_usd,
                "Valor Total": val_pos_usd + accumulated_fees_usd,
                "HODL Value": val_hodl_now
            })
            
        return pd.DataFrame(results), lower_price, upper_price
