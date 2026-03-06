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
        logger.info(f"Conectado a OpenSearch en {es_host}")
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
            
            from .models import Jugador
            import json
            
            print("\nIndexando jugadores...")
            
            # Crear índice si no existe
            try:
                opensearch_client.indices.create(
                    index='jugadores',
                    body=JUGADORES_MAPPING,
                    ignore=400
                )
                logger.info("Índice 'jugadores' creado o ya existe")
            except Exception as e:
                logger.warning(f"Error creando índice: {str(e)}")
            
            jugadores = Jugador.objects.all()
            total = jugadores.count()
            print(f"Total jugadores a indexar: {total}")
            
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
                            logger.warning(f"Algunos documentos fallaron en bulk: {response}")
                        print(f"Indexados {contador}/{total} jugadores...")
                    except Exception as e:
                        logger.error(f"Error en bulk indexing: {str(e)}")
                    operations = []
            
            # Indexar los restantes
            if operations:
                try:
                    body = '\n'.join(operations) + '\n'
                    response = opensearch_client.bulk(body=body)
                    if response.get('errors'):
                        logger.warning(f"Algunos documentos fallaron: {response}")
                except Exception as e:
                    logger.error(f"Error en bulk indexing final: {str(e)}")
            
            logger.info(f"{contador} jugadores indexados")
            print(f"Indexados {contador} jugadores correctamente\n")
        except Exception as e:
            logger.error(f"Error indexando jugadores: {str(e)}")
            print(f"Error indexando jugadores: {str(e)}\n")

    def indexar_equipos():
        """Indexa todos los equipos en OpenSearch"""
        try:
            if not opensearch_client:
                logger.error("OpenSearch client no disponible")
                return
            
            from .models import Equipo
            import json
            
            print("Indexando equipos...")
            
            # Crear índice si no existe
            try:
                opensearch_client.indices.create(
                    index='equipos',
                    body=EQUIPOS_MAPPING,
                    ignore=400
                )
                logger.info("Índice 'equipos' creado o ya existe")
            except Exception as e:
                logger.warning(f"Error creando índice: {str(e)}")
            
            equipos = Equipo.objects.all()
            total = equipos.count()
            print(f"Total equipos a indexar: {total}")
            
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
                            logger.warning(f"Algunos documentos fallaron en bulk: {response}")
                        print(f"Indexados {contador}/{total} equipos...")
                    except Exception as e:
                        logger.error(f"Error en bulk indexing: {str(e)}")
                    operations = []
            
            # Indexar los restantes
            if operations:
                try:
                    body = '\n'.join(operations) + '\n'
                    response = opensearch_client.bulk(body=body)
                    if response.get('errors'):
                        logger.warning(f"Algunos documentos fallaron: {response}")
                except Exception as e:
                    logger.error(f"Error en bulk indexing final: {str(e)}")
            
            logger.info(f"{contador} equipos indexados")
            print(f"Indexados {contador} equipos correctamente\n")
        except Exception as e:
            logger.error(f"Error indexando equipos: {str(e)}")
            print(f"Error indexando equipos: {str(e)}\n")

    def reindexar_todo():
        """Re-indexa todos los documentos"""
        indexar_jugadores()
        indexar_equipos()
        logger.info("Indexación completada")

else:
    # Stubs cuando OpenSearch no está disponible
    opensearch_client = None
    
    def indexar_jugadores():
        logger.error("OpenSearch no esta disponible. Instalalo ejecutando: pip install -r requirements.txt")
    
    def indexar_equipos():
        logger.error("OpenSearch no esta disponible. Instalalo ejecutando: pip install -r requirements.txt")
    
    def reindexar_todo():
        logger.error("OpenSearch no esta disponible. Instalalo ejecutando: pip install -r requirements.txt")
