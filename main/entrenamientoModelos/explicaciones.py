"""
Módulo de Explicaciones XAI para todas las posiciones
=====================================================
Módulo de compatibilidad que redirige a explicaciones_unificadas.py
"""

from explicaciones_unificadas import (
    EXPLICACIONES_PORTERO,
    EXPLICACIONES_DEFENSA,
    EXPLICACIONES_MEDIOCAMPISTA,
    EXPLICACIONES_DELANTERO,
    obtener_explicacion,
    es_valor_alto,
    generar_explicaciones_features
)

# Alias para backward compatibility
EXPLICACIONES_DF = EXPLICACIONES_DEFENSA
EXPLICACIONES_MC = EXPLICACIONES_MEDIOCAMPISTA
EXPLICACIONES_DT = EXPLICACIONES_DELANTERO


def obtener_explicacion_posicion(feature_name, es_positivo, posicion):
    """
    Retorna explicación para cualquier posición.
    
    Nota: Las explicaciones son ahora unificadas para todas las posiciones.
    El parámetro posicion se mantiene para backward compatibility pero no se usa.
    
    Args:
        feature_name: Nombre del feature
        es_positivo: Si el impacto SHAP es positivo
        posicion: (deprecated) 'PT', 'DF', 'MC', 'DT' - no se utiliza
    
    Returns:
        str: Explicación del feature (igual para todas las posiciones)
    """
    return obtener_explicacion(feature_name, es_positivo)
