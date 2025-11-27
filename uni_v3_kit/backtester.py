import pandas as pd
import math
from .math_core import V3Math

class Backtester:
    def __init__(self):
        self.math = V3Math()

    def run_simulation(self, history, investment_usd, range_width_std, days=30, fee_tier=0.003):
        """
        Simula una posición en V3.
        range_width_std: Qué tan ancho es el rango (en Desviaciones Estándar).
        days: Cuántos días atrás mirar.
        """
        if not history: return None
        
        # Filtramos los datos al periodo deseado (history viene ordenado nuevo->viejo)
        # Necesitamos orden cronológico (viejo->nuevo) para simular
        sim_data = history[:days*3][::-1] 
        
        if not sim_data: return None

        # 1. Configuración Inicial (Día 0 de la simulación)
        start_point = sim_data[0]
        p_entry = start_point.get('priceNative', 0) or start_point.get('priceUsd', 0)
        
        if p_entry == 0: return None

        # Calcular Volatilidad previa para decidir el rango (usamos un valor fijo o calculado)
        # Para simplificar, usamos una volatilidad base del 50% anual o la calculada
        # Rango: Precio +/- (Volatilidad * K)
        # K = range_width_std (ej: 2 SD)
        
        # Definimos límites fijos (Estrategia: Set & Forget)
        # Rango porcentual aproximado basado en SD
        # Volatilidad diaria aprox = 3% -> 30 dias = ~16%
        # Rango = Precio * (1 +/- width)
        
        lower_price = p_entry * (1 - range_width_std)
        upper_price = p_entry * (1 + range_width_std)
        
        # Calculamos Liquidez Inicial
        liquidity = self.math.get_liquidity_for_amount(investment_usd, p_entry, lower_price, upper_price)
        
        results = []
        accumulated_fees = 0.0
        
        for snap in sim_data:
            p_current = snap.get('priceNative', 0) or snap.get('priceUsd', 0)
            vol_24h = float(snap.get('Volume', 0))
            liq_pool = float(snap.get('Liquidity', 0)) # Esto es TVL en USD, no L pura. Aproximación necesaria.
            
            if p_current == 0: continue
            
            # --- A. Estado de la Posición ---
            in_range = lower_price <= p_current <= upper_price
            
            # --- B. Cálculo de Fees (Estimado) ---
            # Si estamos en rango, ganamos fees proporcionales
            # Nota: Usamos una heurística porque no tenemos L pura del pool, solo TVL USD.
            # Fee Yield Diario aprox = (Vol / TVL) * FeeTier
            # Tu ganancia = Tu Inversión * Fee Yield * (Concentración)
            # Factor de Concentración V3 ~= 1 / (1 - sqrt(Pa/Pb)) (aprox 2x-5x)
            
            fees_earned = 0
            if in_range and liq_pool > 0:
                # Rendimiento base del pool en este snapshot (aprox 8h)
                base_yield = (vol_24h * fee_tier) / liq_pool / 3 # /3 porque son snapshots de 8h aprox
                
                # Multiplicador de eficiencia por rango concentrado
                # Cuanto más estrecho, más fees (y más riesgo)
                try:
                    concentracion = p_current / (math.sqrt(p_current) * (math.sqrt(upper_price) - math.sqrt(lower_price)))
                except:
                    concentracion = 1
                
                # Capamos concentración a valores realistas (ej. max 50x)
                concentracion = min(concentracion, 50)
                
                fees_earned = investment_usd * base_yield * concentracion
            
            accumulated_fees += fees_earned
            
            # --- C. Valor del Principal (Impermanent Loss) ---
            # Cuánto vale mi posición ahora vs si hubiera holdeado
            # Valor Hold = Inversión inicial ajustada al cambio de precio (50/50 split original aprox)
            # Valor V3 = Depende de la curva
            
            # Cálculo simplificado de IL para reporte
            # Si precio sube 10%, HODL sube 5% (si 50/50). V3 sube menos.
            price_ratio = p_current / p_entry
            
            # Valor Portafolio (Simplificado)
            portfolio_value = investment_usd * math.sqrt(price_ratio) # Aproximación curva V2/V3
            
            # Si se sale de rango, el valor se estanca en el del token que te quedaste
            if p_current < lower_price:
                # Te quedaste con Token Base, cae con el precio
                portfolio_value = investment_usd * (p_current / p_entry)
            elif p_current > upper_price:
                # Te quedaste con Token Quote, valor fijo
                portfolio_value = investment_usd * (math.sqrt(upper_price/p_entry)) # Se congela en la subida
            
            total_value = portfolio_value + accumulated_fees
            
            results.append({
                "Date": snap.get('date'), # Timestamp string
                "Price": p_current,
                "In Range": "✅" if in_range else "❌",
                "Fees Acum": accumulated_fees,
                "Valor Principal": portfolio_value,
                "Valor Total": total_value,
                "HODL Value": investment_usd * (1 + (price_ratio - 1) * 0.5) # Benchmark 50/50
            })
            
        return pd.DataFrame(results), lower_price, upper_price
