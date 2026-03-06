"""Cache utilities para optimizar rendimiento sin perder contenido actualizado"""

from django.core.cache import cache
from rest_framework.response import Response
from functools import wraps
import hashlib
import json


def cache_api_response(timeout=60, key_prefix=''):
    """
    Cachea DATOS de respuesta de API por N segundos.
    NO cachea el objeto Response (no es serializable), solo los datos.
    
    Uso:
    @cache_api_response(timeout=60)
    def get(self, request):
        ...
        return Response(data)
    
    El caché se invalida automáticamente después del timeout.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Construir clave única basada en URL completa y parámetros
            query_string = request.GET.urlencode()
            cache_key = f"{key_prefix}:{request.path}:{query_string}"
            
            # Simplificar la clave si es muy larga
            if len(cache_key) > 250:
                cache_key = f"{key_prefix}:{hashlib.md5(cache_key.encode()).hexdigest()}"
            
            # Intentar obtener del caché
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return Response(cached_data)
            
            # Si no está en caché, ejecutar la función
            response = func(self, request, *args, **kwargs)
            
            # Cachear solo los DATOS, no el Response object
            if isinstance(response, Response) and response.data:
                cache.set(cache_key, response.data, timeout)
            
            return response
        return wrapper
    return decorator


def invalidate_cache_patterns(*patterns):
    """
    Invalida todos los cachés que matcheen con los patrones.
    
    Uso:
    invalidate_cache_patterns('estadisticas:*', 'menu:*')
    """
    # Django LocMemCache no tiene invalidación por patrón,
    # pero podemos implementar una lista de keys conocidas
    pass

