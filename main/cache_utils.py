from django.core.cache import cache
from rest_framework.response import Response
from functools import wraps
import hashlib
import json


def cache_api_response(timeout=60, key_prefix=''):
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            query_string = request.GET.urlencode()
            cache_key = f"{key_prefix}:{request.path}:{query_string}"
            
            if len(cache_key) > 250:
                cache_key = f"{key_prefix}:{hashlib.md5(cache_key.encode()).hexdigest()}"
            
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return Response(cached_data)
            
            response = func(self, request, *args, **kwargs)
            
            if isinstance(response, Response) and response.data:
                cache.set(cache_key, response.data, timeout)
            
            return response
        return wrapper
    return decorator

