import pandas as pd
import math
from datetime import datetime
from .math_core import V3Math

class Backtester:
    def __init__(self):
        self.math = V3Math()

    def _parse_date(self, date_val):
        """Convierte cadenas tipo 20251028140001 a objetos datetime reales"""
        try:
            s = str(date_val)
            # Formato esperado: YYYY MM DD HH MM SS
            return datetime.strptime(s, "%Y%m%d%H%M%S")
        except:
            return date_val

    def run_simulation(self, history, investment_usd, range_width_std, days=30, fee_tier=0.003):
        """
        Simula la posición usando los datos históricos de APR y Precio.
        """
        if not history: return None
        
        # Filtramos los datos al periodo deseado (history viene ordenado nuevo->viejo)
        # Necesitamos orden cronológico (viejo->nuevo) para simular la evolución
        sim_data = history[:days*3][::-1] 
        
        if not sim_data: return None

        # --- 1. Configuración Inicial (Día 0) ---
        start_point = sim_data[0]
        
        # Obtenemos precio de entrada (Prioridad precio nativo)
        p_entry = start_point.get('priceNative')
        if p_entry is None: p_entry = start_point.get('priceUsd', 0)
        
        if p_entry == 0: return None

        # Definimos los límites del Rango (Estrategia Set & Forget)
        lower_price = p_entry * (1 - range_width_std)
        upper_price = p_entry * (1 + range_width_std)
        
        results = []
        accumulated_fees = 0.0
        
        # --- 2. Bucle de Simulación ---
        for snap in sim_data:
            # Precio actual del snapshot
            p_current = snap.get('priceNative')
            if p_current is None: p_current = snap.get('priceUsd', 0)
            
            # Fecha formateada para el gráfico
            raw_date = snap.get('date')
            formatted_date = self._parse_date(raw_date)
            
            if p_current == 0: continue
            
            # A. Estado: ¿Está el precio dentro de nuestro rango?
            in_range = lower_price <= p_current <= upper_price
            
            # B. Cálculo de Fees usando el APR reportado
            fees_earned_period = 0.0
            
            # Obtenemos el APR reportado en este snapshot (ej: 50.5 para 50.5%)
            apr_snapshot = snap.get('apr', 0)
            
            if in_range and apr_snapshot:
                # Lógica de usuario: APR anual / 1095 periodos (365 días * 3 snapshots de 8h)
                # 1. Convertir APR de porcentaje a decimal: 50.5 -> 0.505
                # 2. Dividir por los periodos anuales
                period_yield = (float(apr_snapshot) / 100.0) / (365.0 * 3.0)
                
                # Ganancia = Inversión * Yield del periodo
                fees_earned_period = investment_usd * period_yield
            
            accumulated_fees += fees_earned_period
            
            # C. Valor del Principal (Impermanent Loss)
            # Calculamos cuánto varía el valor de los tokens subyacentes vs holdear
            price_ratio = p_current / p_entry
            
            if in_range:
                # Fórmula simplificada de valor V3 dentro de rango
                portfolio_value = investment_usd * math.sqrt(price_ratio)
            elif p_current < lower_price:
                # Precio cayó por debajo del rango -> Tenemos 100% Token Base (que se devalúa)
                portfolio_value = investment_usd * (p_current / p_entry)
            else: 
                # Precio subió por encima del rango -> Tenemos 100% Token Quote (valor congelado)
                portfolio_value = investment_usd * (math.sqrt(upper_price/p_entry))
            
            total_value = portfolio_value + accumulated_fees
            
            results.append({
                "Date": formatted_date,
                "Price": p_current,
                "In Range": in_range, # Booleano útil para pintar gráficos de colores
                "Fees Acum": accumulated_fees,
                "Valor Principal": portfolio_value,
                "Valor Total": total_value,
                "HODL Value": investment_usd * (1 + (price_ratio - 1) * 0.5) # Benchmark 50/50
            })
            
        return pd.DataFrame(results), lower_price, upper_price
