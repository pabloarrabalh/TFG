import json
import os

from dotenv import load_dotenv

from .models import Equipo, Jugador

# Cargar variables de entorno
load_dotenv()

OPENSEARCH_AVAILABLE = False
opensearch_client = None

try:
    from opensearchpy import OpenSearch
except ImportError:
    OpenSearch = None


if OpenSearch is not None:
    es_host = os.getenv('OPENSEARCH_HOST', 'localhost:9200')
    if not es_host.startswith('http://') and not es_host.startswith('https://'):
        es_host = f'http://{es_host}'

    try:
        opensearch_client = OpenSearch(
            hosts=[es_host],
            use_ssl=False,
            verify_certs=False,
            request_timeout=30,
        )
        opensearch_client.info()
        OPENSEARCH_AVAILABLE = True
    except Exception:
        OPENSEARCH_AVAILABLE = False


if OPENSEARCH_AVAILABLE:
    JUGADORES_MAPPING = {
        "settings": {
            "index.number_of_shards": 1,
            "index.number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "spanish": {
                        "type": "standard",
                        "stopwords": "_spanish_"
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "id": {"type": "integer"},
                "nombre_completo": {"type": "text", "analyzer": "spanish"},
                "nombre": {"type": "text", "analyzer": "spanish"},
                "apellido": {"type": "text", "analyzer": "spanish"},
                "nacionalidad": {"type": "keyword"},
                "posicion": {"type": "keyword"}
            }
        }
    }
    
    EQUIPOS_MAPPING = {
        "settings": {
            "index.number_of_shards": 1,
            "index.number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "spanish": {
                        "type": "standard",
                        "stopwords": "_spanish_"
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "id": {"type": "integer"},
                "nombre": {"type": "text", "analyzer": "spanish"},
                "estadio": {"type": "text", "analyzer": "spanish"}
            }
        }
    }

    def indexar_jugadores():
        try:
            if not opensearch_client:
                return
            
            try:
                opensearch_client.indices.create(
                    index='jugadores',
                    body=JUGADORES_MAPPING,
                    ignore=400
                )
            except Exception:
                pass
            
            jugadores = Jugador.objects.all()
            total = jugadores.count()
            
            if total == 0:
                return
            
            # Bulk indexing
            operations = []
            contador = 0
            
            for jugador in jugadores:
                operations.append(json.dumps({
                    "index": {"_index": "jugadores", "_id": jugador.id}
                }))
                
                doc = {
                    'id': jugador.id,
                    'nombre_completo': f"{jugador.nombre} {jugador.apellido}",
                    'nombre': jugador.nombre,
                    'apellido': jugador.apellido,
                    'nacionalidad': jugador.nacionalidad,
                    'posicion': jugador.get_posicion_mas_frecuente() or 'Desconocida'
                }
                operations.append(json.dumps(doc))
                contador += 1
                
                # Indexar en lotes de 100
                if contador % 100 == 0:
                    try:
                        body = '\n'.join(operations) + '\n'
                        response = opensearch_client.bulk(body=body)
                        if response.get('errors'):
                            pass
                    except Exception:
                        pass
                    operations = []
            
            if operations:
                try:
                    body = '\n'.join(operations) + '\n'
                    response = opensearch_client.bulk(body=body)
                    if response.get('errors'):
                        pass
                except Exception:
                    pass
        except Exception:
            return

    def indexar_equipos():
        try:
            if not opensearch_client:
                return
            
            try:
                opensearch_client.indices.create(
                    index='equipos',
                    body=EQUIPOS_MAPPING,
                    ignore=400
                )
            except Exception:
                pass
            
            equipos = Equipo.objects.all()
            total = equipos.count()
            
            if total == 0:
                return
            
            operations = []
            contador = 0
            
            for equipo in equipos:
                operations.append(json.dumps({
                    "index": {"_index": "equipos", "_id": equipo.id}
                }))
                
                doc = {
                    'id': equipo.id,
                    'nombre': equipo.nombre,
                    'estadio': equipo.estadio or 'Desconocido'
                }
                operations.append(json.dumps(doc))
                contador += 1
                
                # Indexar en lotes de 100
                if contador % 100 == 0:
                    try:
                        body = '\n'.join(operations) + '\n'
                        response = opensearch_client.bulk(body=body)
                        if response.get('errors'):
                            pass
                    except Exception:
                        pass
                    operations = []
            
            if operations:
                try:
                    body = '\n'.join(operations) + '\n'
                    response = opensearch_client.bulk(body=body)
                    if response.get('errors'):
                        pass
                except Exception:
                    pass
        except Exception:
            return

    def reindexar_todo():
        indexar_jugadores()
        indexar_equipos()

else:
    #Solo en local, no debería llegar nunca al desplegar
    opensearch_client = None
    
    def indexar_jugadores():
        pass
    
    def indexar_equipos():
        pass
    
    def reindexar_todo():
        pass
