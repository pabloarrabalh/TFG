import json
import logging
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger(__name__)

# Intentar importar opensearch-py - es opcional
OPENSEARCH_AVAILABLE = False

try:
    from opensearchpy import OpenSearch
    from .models import Jugador, Equipo
    
    # Obtener configuración de variables de entorno
    es_host = os.getenv('OPENSEARCH_HOST', 'localhost:9200')
    es_user = os.getenv('OPENSEARCH_USER', 'admin')
    es_password = os.getenv('OPENSEARCH_PASSWORD', 'admin')
    
    # Configurar conexión a OpenSearch
    opensearch_client = None
    try:
        # Asegurar que el host tenga el esquema http://
        if not es_host.startswith('http://') and not es_host.startswith('https://'):
            es_host = f'http://{es_host}'
        
        opensearch_client = OpenSearch(
            hosts=[es_host],
            use_ssl=False,
            verify_certs=False,
            request_timeout=30
        )
        # Probar conexión
        opensearch_client.info()
        OPENSEARCH_AVAILABLE = True
    except Exception as e:
        OPENSEARCH_AVAILABLE = False
        logger.warning(f"No se pudo conectar a OpenSearch: {str(e)}")
        logger.warning("La busqueda por OpenSearch no estara disponible")

except ImportError:
    logger.warning("opensearch-py no esta instalado. Ejecuta: pip install -r requirements.txt")
    OPENSEARCH_AVAILABLE = False


if OPENSEARCH_AVAILABLE:
    # Mappings para indexing en OpenSearch
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
        """Indexa todos los jugadores en OpenSearch"""
        try:
            if not opensearch_client:
                logger.error("OpenSearch client no disponible")
                return
            
            # Crear índice si no existe
            try:
                opensearch_client.indices.create(
                    index='jugadores',
                    body=JUGADORES_MAPPING,
                    ignore=400
                )
            except Exception as e:
                logger.warning(f"Error creando índice jugadores: {str(e)}")
            
            jugadores = Jugador.objects.all()
            total = jugadores.count()
            
            if total == 0:
                logger.warning("No hay jugadores para indexar")
                return
            
            # Bulk indexing
            operations = []
            contador = 0
            
            for jugador in jugadores:
                # Acción de index
                operations.append(json.dumps({
                    "index": {"_index": "jugadores", "_id": jugador.id}
                }))
                
                # Documento
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
                            logger.warning(f"Bulk error (jugadores): {response}")
                    except Exception as e:
                        logger.error(f"Error en bulk indexing: {str(e)}")
                    operations = []
            
            # Indexar los restantes
            if operations:
                try:
                    body = '\n'.join(operations) + '\n'
                    response = opensearch_client.bulk(body=body)
                    if response.get('errors'):
                        logger.warning(f"Bulk error final (jugadores): {response}")
                except Exception as e:
                    logger.error(f"Error en bulk indexing final: {str(e)}")
        except Exception as e:
            logger.error(f"Error indexando jugadores: {str(e)}")

    def indexar_equipos():
        """Indexa todos los equipos en OpenSearch"""
        try:
            if not opensearch_client:
                logger.error("OpenSearch client no disponible")
                return
            
            # Crear índice si no existe
            try:
                opensearch_client.indices.create(
                    index='equipos',
                    body=EQUIPOS_MAPPING,
                    ignore=400
                )
            except Exception as e:
                logger.warning(f"Error creando índice equipos: {str(e)}")
            
            equipos = Equipo.objects.all()
            total = equipos.count()
            
            if total == 0:
                logger.warning("No hay equipos para indexar")
                return
            
            # Bulk indexing
            operations = []
            contador = 0
            
            for equipo in equipos:
                # Acción de index
                operations.append(json.dumps({
                    "index": {"_index": "equipos", "_id": equipo.id}
                }))
                
                # Documento
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
                            logger.warning(f"Bulk error (equipos): {response}")
                    except Exception as e:
                        logger.error(f"Error en bulk indexing: {str(e)}")
                    operations = []
            
            # Indexar los restantes
            if operations:
                try:
                    body = '\n'.join(operations) + '\n'
                    response = opensearch_client.bulk(body=body)
                    if response.get('errors'):
                        logger.warning(f"Bulk error final (equipos): {response}")
                except Exception as e:
                    logger.error(f"Error en bulk indexing final: {str(e)}")
        except Exception as e:
            logger.error(f"Error indexando equipos: {str(e)}")

    def reindexar_todo():
        """Re-indexa todos los documentos"""
        indexar_jugadores()
        indexar_equipos()

else:
    # Stubs cuando OpenSearch no está disponible
    opensearch_client = None
    
    def indexar_jugadores():
        pass
    
    def indexar_equipos():
        pass
    
    def reindexar_todo():
        pass
