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

    # --- FUNCIONES PARA BACKTESTING V3 ---

    @staticmethod
    def get_liquidity_for_amount(amount_usd, price_current, price_min, price_max):
        """Estima la Liquidez (L) para una inversión en USD dado un rango."""
        if price_current <= price_min or price_current >= price_max:
            return 0 
            
        sqrt_p = math.sqrt(price_current)
        sqrt_a = math.sqrt(price_min)
        sqrt_b = math.sqrt(price_max)
        
        # Cantidades teóricas para L=1
        amount_y = sqrt_p - sqrt_a
        amount_x = (1/sqrt_p) - (1/sqrt_b)
        
        val_unit_l = (amount_x * price_current) + amount_y
        
        if val_unit_l == 0: return 0
        
        return amount_usd / val_unit_l

    @staticmethod
    def estimate_fees(liquidity, total_liquidity_pool, volume_24h, fee_tier_decimal):
        """Estima fees usando cuota de mercado (Modelo Volumen)."""
        if total_liquidity_pool == 0: return 0
        share = liquidity / total_liquidity_pool
        pool_fees = volume_24h * fee_tier_decimal
        return pool_fees * share

    @staticmethod
    def calculate_amounts(liquidity, sqrt_p, sqrt_a, sqrt_b):
        """Devuelve cantidad de Token X e Y dado L y precios."""
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

    # --- NUEVO: Eficiencia de Capital V3 (Multiplicador) ---
    @staticmethod
    def calculate_concentration_multiplier(range_width_pct):
        """
        Calcula el multiplicador de eficiencia de capital.
        range_width_pct: Porcentaje de desviación (ej 0.10 para 10%)
        """
        try:
            # Evitamos división por cero o anchos negativos/nulos
            w = max(range_width_pct, 0.001) 
            
            # Relación de precios P_min / P_max para un rango simétrico
            # P_min = P * (1 - w)
            # P_max = P * (1 + w)
            # Ratio = (1 - w) / (1 + w)
            ratio = (1 - w) / (1 + w)
            
            # Fórmula: Multiplicador = 1 / (1 - sqrt(ratio))
            multiplier = 1 / (1 - math.sqrt(ratio))
            
            # Capamos a un máximo razonable (100x) para seguridad numérica
            return min(multiplier, 100.0)
        except:
            return 1.0
