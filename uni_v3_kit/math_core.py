import math
import numpy as np

class V3Math:
    @staticmethod
    def calculate_realized_volatility(price_history):
        """Calcula volatilidad real basada en precios pasados"""
        if len(price_history) < 5: return 0.80 # Si es muy nuevo, asumimos riesgo alto
        
        try:
            # Convertimos a array de números
            prices = np.array(price_history, dtype=float)
            # Filtramos ceros para evitar errores matemáticos
            prices = prices[prices > 0]
            if len(prices) < 2: return 0.80

            # Retornos logarítmicos
            returns = np.diff(np.log(prices))
            std_dev = np.std(returns)
            
            # Anualizamos (Raíz de 365 días)
            return std_dev * math.sqrt(365)
        except:
            return 0.80

    @staticmethod
    def calculate_il_risk_cost(volatility_annual):
        """Costo teórico por volatilidad (LVR)"""
        return (volatility_annual ** 2) / 2
