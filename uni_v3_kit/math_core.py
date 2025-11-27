import math
import numpy as np

class V3Math:
    @staticmethod
    def calculate_realized_volatility(price_history):
        """Calcula volatilidad real basada en precios pasados"""
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

    # --- NUEVAS FUNCIONES PARA BACKTESTING V3 ---

    @staticmethod
    def get_liquidity_for_amount(amount_usd, price_current, price_min, price_max):
        """
        Estima la Liquidez (L) que consigues con una inversión en USD
        dado un rango y precio actual.
        """
        if price_current <= price_min or price_current >= price_max:
            return 0 # Fuera de rango no entramos en el simulador simplificado
            
        sqrt_p = math.sqrt(price_current)
        sqrt_a = math.sqrt(price_min)
        sqrt_b = math.sqrt(price_max)
        
        # Fórmula simplificada: Asumimos que depositamos óptimamente
        # L = Amount / (Costo unitario de liquidez en USD)
        
        # Costo de 1 unidad de L en Token 0 (Quote) y Token 1 (Base)
        # Nota: Simplificación para estimación rápida en backtest
        # Cantidad de Y (Quote) necesaria
        amount_y = sqrt_p - sqrt_a
        # Cantidad de X (Base) necesaria
        amount_x = (1/sqrt_p) - (1/sqrt_b)
        
        # Valor total de 1 unidad de L en USD
        val_unit_l = (amount_x * price_current) + amount_y
        
        if val_unit_l == 0: return 0
        
        L = amount_usd / val_unit_l
        return L

    @staticmethod
    def estimate_fees(liquidity, total_liquidity_pool, volume_24h, fee_tier_decimal):
        """
        Estima fees ganadas en un periodo de 24h.
        Suposición: El precio se mantuvo en rango (simplificación).
        """
        if total_liquidity_pool == 0: return 0
        
        # Share of Pool
        share = liquidity / total_liquidity_pool
        
        # Fees totales del pool
        pool_fees = volume_24h * fee_tier_decimal
        
        return pool_fees * share

    @staticmethod
    def calculate_amounts(liquidity, sqrt_p, sqrt_a, sqrt_b):
        """Devuelve cantidad de Token X e Y dado L y precios"""
        # Si P < Pa -> Todo en X
        if sqrt_p <= sqrt_a:
            amount_x = liquidity * (sqrt_b - sqrt_a) / (sqrt_a * sqrt_b)
            amount_y = 0
        # Si P > Pb -> Todo en Y
        elif sqrt_p >= sqrt_b:
            amount_x = 0
            amount_y = liquidity * (sqrt_b - sqrt_a)
        # En rango
        else:
            amount_x = liquidity * (sqrt_b - sqrt_p) / (sqrt_p * sqrt_b)
            amount_y = liquidity * (sqrt_p - sqrt_a)
            
        return amount_x, amount_y
