#!/usr/bin/env python
"""
Script de verificación: asegura que OpenSearch está corriendo y configurado correctamente
Ejecución: python scripts/check_opensearch.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.opensearch_docs import OPENSEARCH_AVAILABLE, opensearch_client
import logging

logger = logging.getLogger(__name__)

def check_opensearch():
    """Verifica que OpenSearch está disponible y configurado"""
    print("\n" + "="*80)
    print("VERIFICACIÓN DE OPENSEARCH")
    print("="*80)
    
    # 1. Verificar disponibilidad
    if not OPENSEARCH_AVAILABLE:
        print("\n❌ CRÍTICO: OpenSearch NO está disponible")
        print("\nAsegurate de que:")
        print("  1. OpenSearch está corriendo en localhost:9200")
        print("  2. Puedes conectarte: curl -u admin:admin http://localhost:9200")
        print("  3. Has configurado las variables de entorno en .env:")
        print("     - OPENSEARCH_HOST=localhost:9200")
        print("     - OPENSEARCH_USER=admin")
        print("     - OPENSEARCH_PASSWORD=admin")
        print("  4. Reinicia el servidor Django después de arreglarlo")
        return False
    
    print("\n✓ OpenSearch está disponible")
    
    # 2. Verificar conexión
    if not opensearch_client:
        print("❌ No se pudo crear el cliente de OpenSearch")
        return False
    
    print("✓ Conexión a OpenSearch establecida")
    
    # 3. Verificar índices
    try:
        indices = opensearch_client.indices.get_mapping(index='*')
        index_names = list(indices.keys())
        print(f"\n✓ Índices encontrados: {index_names}")
        
        # Verificar que jugadores y equipos existan
        if 'jugadores' not in index_names:
            print("  ⚠️  Índice 'jugadores' no encontrado - se creará al indexar")
        else:
            count = opensearch_client.count(index='jugadores')
            print(f"  ✓ 'jugadores': {count['count']} documentos")
        
        if 'equipos' not in index_names:
            print("  ⚠️  Índice 'equipos' no encontrado - se creará al indexar")
        else:
            count = opensearch_client.count(index='equipos')
            print(f"  ✓ 'equipos': {count['count']} documentos")
    except Exception as e:
        print(f"❌ Error verificando índices: {e}")
        return False
    
    # 4. Test de búsqueda
    print("\n🔍 Probando búsqueda...")
    try:
        # Intentar búsqueda de prueba
        search_body = {
            "query": {
                "match_all": {}
            },
            "size": 1
        }
        
        response = opensearch_client.search(index='jugadores', body=search_body)
        hit_count = response['hits']['total']['value']
        print(f"✓ Búsqueda funciona ({hit_count} documentos encontrados)")
    except Exception as e:
        print(f"❌ Error en búsqueda: {e}")
        return False
    
    print("\n" + "="*80)
    print("✅ OPENSEARCH ESTÁ CORRECTAMENTE CONFIGURADO")
    print("="*80 + "\n")
    return True

if __name__ == '__main__':
    success = check_opensearch()
    sys.exit(0 if success else 1)
