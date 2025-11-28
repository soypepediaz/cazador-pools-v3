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

    # --- CÁLCULO EXACTO DE IL EN V3 ---
    @staticmethod
    def calculate_v3_il_at_limit(range_width_pct):
        """
        Calcula el Impermanent Loss exacto de Uniswap V3 al tocar el límite del rango.
        Simulamos una posición unitaria para ver la pérdida porcentual.
        """
        try:
            w = max(range_width_pct, 0.001)
            
            # Definimos escenario normalizado:
            P_entry = 1.0
            P_min = 1.0 * (1 - w)
            P_max = 1.0 * (1 + w)
            
            # Asumimos que queremos calcular el IL en el peor caso (tocar límite)
            # Generalmente el IL es simétrico en % si el rango es simétrico geométricamente,
            # pero aquí usamos rango simétrico aritmético (1 +/- w), así que probamos ambos límites
            # y devolvemos el peor (mayor pérdida).
            
            il_lower = V3Math._get_il_for_price_move(P_entry, P_min, P_min, P_max)
            il_upper = V3Math._get_il_for_price_move(P_entry, P_max, P_min, P_max)
            
            return max(abs(il_lower), abs(il_upper))
        except:
            return 0.0

    @staticmethod
    def _get_il_for_price_move(P0, P1, Pa, Pb):
        """
        Calcula IL moviéndose de P0 a P1 dentro de un rango [Pa, Pb].
        Retorna: (ValorPool - ValorHodl) / ValorHodl
        """
        # 1. Calcular Liquidez (L) para una inversión arbitraria (ej. 1000 USD) en P0
        investment = 1000.0
        
        # Calcular cantidades iniciales (x0, y0)
        L = V3Math.get_liquidity_for_amount(investment, P0, Pa, Pb)
        if L == 0: return 0.0
        
        x0, y0 = V3Math.calculate_amounts(L, math.sqrt(P0), math.sqrt(Pa), math.sqrt(Pb))
        
        # 2. Calcular Valor HODL en P1
        # Si hubiéramos guardado x0 y y0
        val_hodl = (x0 * P1) + y0
        
        # 3. Calcular Valor Pool en P1
        # Nuevas cantidades x1, y1 en el precio P1
        x1, y1 = V3Math.calculate_amounts(L, math.sqrt(P1), math.sqrt(Pa), math.sqrt(Pb))
        val_pool = (x1 * P1) + y1
        
        # 4. Impermanent Loss
        if val_hodl == 0: return 0.0
        return (val_pool - val_hodl) / val_hodl

    # --- Funciones de Liquidez Estándar ---
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

    @staticmethod
    def calculate_concentration_multiplier(range_width_pct):
        try:
            w = max(range_width_pct, 0.001) 
            ratio = (1 - w) / (1 + w)
            multiplier = 1 / (1 - math.sqrt(ratio))
            return min(multiplier, 100.0)
        except:
            return 1.0
