import math
import numpy as np

class V3Math:
    @staticmethod
    def calculate_realized_volatility(price_history):
        """Calcula volatilidad anualizada basada en precios pasados"""
        if len(price_history) < 5: return 0.80 
        try:
            prices = np.array(price_history, dtype=float)
            prices = prices[prices > 0]
            if len(prices) < 2: return 0.80
            returns = np.diff(np.log(prices))
            std_dev = np.std(returns)
            return std_dev * math.sqrt(365)
        except:
            return 0.80

    @staticmethod
    def calculate_il_risk_cost(volatility_annual):
        return (volatility_annual ** 2) / 2

    # --- NUEVO: Cálculo de IL en el límite del rango ---
    @staticmethod
    def calculate_v3_il_at_limit(range_width_pct):
        """
        Calcula el % de Impermanent Loss (vs HODL) justo en el momento 
        en que el precio toca el límite superior o inferior del rango.
        
        Asumimos rango simétrico P * (1 +/- width).
        En el límite, la posición V3 vale menos que el HODL.
        """
        try:
            w = range_width_pct
            # Relación de precio al llegar al límite superior (o inverso del inferior)
            # ratio = P_exit / P_entry = 1 + w
            ratio = 1 + w
            sqrt_ratio = math.sqrt(ratio)
            
            # Valor HODL en el límite (50/50 inicial): 0.5 + 0.5 * ratio
            val_hodl = 0.5 + (0.5 * ratio)
            
            # Valor V3 en el límite (Estrategia 100% liquidez en rango):
            # Fórmula simplificada de IL para rango completo aplicada al ratio
            # IL_v2 = (2 * sqrt_ratio / (1 + ratio)) - 1
            # Pero en V3 concentrado, si sales del rango, el IL es la diferencia
            # entre haber vendido progresivamente vs mantener.
            
            # Usamos la aproximación estándar de IL para un movimiento de precio 'ratio'
            # IL = 2 * sqrt(ratio) / (1 + ratio) - 1
            # Nota: Esta fórmula es universal para CPMM (x*y=k) que es lo que rige dentro del rango.
            
            il_decimal = (2 * sqrt_ratio / (1 + ratio)) - 1
            
            # Devolvemos el valor absoluto positivo del costo (ej: 0.015 para 1.5% de pérdida)
            return abs(il_decimal)
        except:
            return 0.0

    @staticmethod
    def calculate_concentration_multiplier(range_width_pct):
        try:
            w = max(range_width_pct, 0.001) 
            ratio = (1 - w) / (1 + w)
            multiplier = 1 / (1 - math.sqrt(ratio))
            return min(multiplier, 100.0)
        except:
            return 1.0
    
    # ... (Resto de funciones de liquidez para backtester se mantienen igual) ...
    @staticmethod
    def get_liquidity_for_amount(amount_usd, price_current, price_min, price_max):
        if price_current <= price_min or price_current >= price_max: return 0 
        sqrt_p = math.sqrt(price_current)
        sqrt_a = math.sqrt(price_min)
        sqrt_b = math.sqrt(price_max)
        amount_y = sqrt_p - sqrt_a
        amount_x = (1/sqrt_p) - (1/sqrt_b)
        val_unit_l = (amount_x * price_current) + amount_y
        if val_unit_l == 0: return 0
        return amount_usd / val_unit_l

    @staticmethod
    def calculate_amounts(liquidity, sqrt_p, sqrt_a, sqrt_b):
        if sqrt_p <= sqrt_a:
            amount_x = liquidity * (sqrt_b - sqrt_a) / (sqrt_a * sqrt_b)
            amount_y = 0
        elif sqrt_p >= sqrt_b:
            amount_x = 0
            amount_y = liquidity * (sqrt_b - sqrt_a)
        else:
            amount_x = liquidity * (sqrt_b - sqrt_p) / (sqrt_p * sqrt_b)
            amount_y = liquidity * (sqrt_p - sqrt_a)
        return amount_x, amount_y
