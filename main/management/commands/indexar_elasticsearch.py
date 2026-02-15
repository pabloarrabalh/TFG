from django.core.management.base import BaseCommand
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Indexa todos los jugadores y equipos en Elasticsearch'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando indexación...'))
        
        try:
            from main.elasticsearch_docs import ELASTICSEARCH_AVAILABLE
            
            if not ELASTICSEARCH_AVAILABLE:
                self.stdout.write(self.style.ERROR(
                    'Elasticsearch no esta disponible\n'
                    'Asegúrate de:\n'
                    '1. Tener Elasticsearch corriendo en localhost:9200\n'
                    '2. Ejecutar en otra ventana:\n'
                    '   - En Windows: C:\\elasticsearch-8.14.0\\bin\\elasticsearch.bat\n'
                    '   - En Mac/Linux: ./bin/elasticsearch'
                ))
                return
            
            from main.elasticsearch_docs import reindexar_todo
            reindexar_todo()
            self.stdout.write(self.style.SUCCESS('Indexacion completada exitosamente'))
            
        except ImportError as e:
            self.stdout.write(self.style.ERROR(
                f'Error de importacion: {str(e)}\n'
                'Ejecuta: pip install -r requirements.txt'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error en indexacion: {str(e)}'))
            logger.exception('Error durante indexación')
