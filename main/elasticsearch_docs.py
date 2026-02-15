import logging
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger(__name__)

# Intentar importar elasticsearch - es opcional
ELASTICSEARCH_AVAILABLE = False

try:
    from elasticsearch_dsl import Document, Text, Keyword, Integer, connections
    from elasticsearch import Elasticsearch
    from .models import Jugador, Equipo
    
    # Obtener configuración de variables de entorno
    es_host = os.getenv('ELASTICSEARCH_HOST')
    es_api_key = os.getenv('ELASTICSEARCH_API_KEY')
    
    # Configurar conexión a Elasticsearch
    try:
        if es_api_key and es_host:
            # Conexión con API key (para Elastic Cloud)
            connections.create_connection(
                alias='default',
                hosts=[es_host],
                api_key=es_api_key,
                verify_certs=True
            )
            logger.info(f"Conectado a Elasticsearch en {es_host} (con API Key)")
            ELASTICSEARCH_AVAILABLE = True
        else:
            logger.warning("Falta ELASTICSEARCH_HOST o ELASTICSEARCH_API_KEY en .env")
            ELASTICSEARCH_AVAILABLE = False
    except Exception as e:
        ELASTICSEARCH_AVAILABLE = False
        logger.warning(f"No se pudo conectar a Elasticsearch: {str(e)}")
        logger.warning("La busqueda por elasticsearch no estara disponible")

except ImportError:
    logger.warning("elasticsearch-dsl no esta instalado. Ejecuta: pip install -r requirements.txt")
    ELASTICSEARCH_AVAILABLE = False


if ELASTICSEARCH_AVAILABLE:
    class JugadorDocument(Document):
        """Documento de Elasticsearch para búsqueda de jugadores"""
        id = Integer()
        nombre_completo = Text(analyzer='spanish')
        nombre = Text(analyzer='spanish')
        apellido = Text(analyzer='spanish')
        nacionalidad = Keyword()
        posicion = Keyword()
        
        class Index:
            name = 'jugadores'
            settings = {
                'analysis': {
                    'analyzer': {
                        'spanish': {
                            'type': 'standard',
                            'stopwords': '_spanish_'
                        }
                    }
                }
            }

    class EquipoDocument(Document):
        """Documento de Elasticsearch para búsqueda de equipos"""
        id = Integer()
        nombre = Text(analyzer='spanish')
        estadio = Text(analyzer='spanish')
        
        class Index:
            name = 'equipos'
            settings = {
                'analysis': {
                    'analyzer': {
                        'spanish': {
                            'type': 'standard',
                            'stopwords': '_spanish_'
                        }
                    }
                }
            }

    def indexar_jugadores():
        """Indexa todos los jugadores en Elasticsearch"""
        try:
            from .models import Jugador
            from elasticsearch import helpers
            
            print("\nIndexando jugadores...")
            
            # Intentar init() pero ignorar errores en serverless mode
            try:
                JugadorDocument.init()
            except Exception as e:
                if '410' not in str(e):
                    logger.warning(f"Error en init (puede ser serverless): {str(e)}")
            
            jugadores = Jugador.objects.all()
            total = jugadores.count()
            print(f"Total jugadores a indexar: {total}")
            
            if total == 0:
                logger.warning("No hay jugadores para indexar")
                return
            
            # Usar bulk para indexar más rápido
            docs = []
            contador = 0
            
            for jugador in jugadores:
                doc = {
                    '_id': jugador.id,
                    'id': jugador.id,
                    'nombre_completo': f"{jugador.nombre} {jugador.apellido}",
                    'nombre': jugador.nombre,
                    'apellido': jugador.apellido,
                    'nacionalidad': jugador.nacionalidad,
                    'posicion': jugador.get_posicion_mas_frecuente() or 'Desconocida'
                }
                docs.append(doc)
                contador += 1
                
                # Indexar en lotes de 100
                if contador % 100 == 0:
                    try:
                        actions = [
                            {
                                '_index': 'jugadores',
                                '_id': d['_id'],
                                '_source': {k: v for k, v in d.items() if k != '_id'}
                            }
                            for d in docs
                        ]
                        from elasticsearch_dsl import connections
                        client = connections.get_connection()
                        helpers.bulk(client, actions, raise_on_error=False)
                        print(f"Indexados {contador}/{total} jugadores...")
                    except Exception as e:
                        logger.error(f"Error en bulk indexing: {str(e)}")
                    docs = []
            
            # Indexar los restantes
            if docs:
                try:
                    actions = [
                        {
                            '_index': 'jugadores',
                            '_id': d['_id'],
                            '_source': {k: v for k, v in d.items() if k != '_id'}
                        }
                        for d in docs
                    ]
                    from elasticsearch_dsl import connections
                    client = connections.get_connection()
                    helpers.bulk(client, actions, raise_on_error=False)
                except Exception as e:
                    logger.error(f"Error en bulk indexing final: {str(e)}")
            
            logger.info(f"{contador} jugadores indexados")
            print(f"Indexados {contador} jugadores correctamente\n")
        except Exception as e:
            logger.error(f"Error indexando jugadores: {str(e)}")
            print(f"Error indexando jugadores: {str(e)}\n")

    def indexar_equipos():
        """Indexa todos los equipos en Elasticsearch"""
        try:
            from .models import Equipo
            from elasticsearch import helpers
            
            print("Indexando equipos...")
            
            # Intentar init() pero ignorar errores en serverless mode
            try:
                EquipoDocument.init()
            except Exception as e:
                if '410' not in str(e):
                    logger.warning(f"Error en init (puede ser serverless): {str(e)}")
            
            equipos = Equipo.objects.all()
            total = equipos.count()
            print(f"Total equipos a indexar: {total}")
            
            if total == 0:
                logger.warning("No hay equipos para indexar")
                return
            
            # Usar bulk para indexar más rápido
            docs = []
            contador = 0
            
            for equipo in equipos:
                doc = {
                    '_id': equipo.id,
                    'id': equipo.id,
                    'nombre': equipo.nombre,
                    'estadio': equipo.estadio or 'Desconocido'
                }
                docs.append(doc)
                contador += 1
                
                # Indexar en lotes
                if contador % 100 == 0:
                    try:
                        actions = [
                            {
                                '_index': 'equipos',
                                '_id': d['_id'],
                                '_source': {k: v for k, v in d.items() if k != '_id'}
                            }
                            for d in docs
                        ]
                        from elasticsearch_dsl import connections
                        client = connections.get_connection()
                        helpers.bulk(client, actions, raise_on_error=False)
                        print(f"Indexados {contador}/{total} equipos...")
                    except Exception as e:
                        logger.error(f"Error en bulk indexing: {str(e)}")
                    docs = []
            
            # Indexar los restantes
            if docs:
                try:
                    actions = [
                        {
                            '_index': 'equipos',
                            '_id': d['_id'],
                            '_source': {k: v for k, v in d.items() if k != '_id'}
                        }
                        for d in docs
                    ]
                    from elasticsearch_dsl import connections
                    client = connections.get_connection()
                    helpers.bulk(client, actions, raise_on_error=False)
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
    # Stubs cuando Elasticsearch no está disponible
    class JugadorDocument:
        pass
    
    class EquipoDocument:
        pass
    
    def indexar_jugadores():
        logger.error("Elasticsearch no esta disponible. Instalalo para usar busqueda.")
    
    def indexar_equipos():
        logger.error("Elasticsearch no esta disponible. Instalalo para usar busqueda.")
    
    def reindexar_todo():
        logger.error("Elasticsearch no esta disponible. Instalalo para usar busqueda.")
