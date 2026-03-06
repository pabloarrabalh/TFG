from django.core.management.base import BaseCommand
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Indexa todos los jugadores y equipos en OpenSearch'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando indexación...'))
        
        try:
            from main.opensearch_docs import OPENSEARCH_AVAILABLE
            
            if not OPENSEARCH_AVAILABLE:
                self.stdout.write(self.style.ERROR(
                    'OpenSearch no esta disponible\n'
                    'Asegúrate de:\n'
                    '1. Tener OpenSearch corriendo en localhost:9200\n'
                    '2. Configurar variables de entorno en .env:\n'
                    '   - OPENSEARCH_HOST=localhost:9200\n'
                    '   - OPENSEARCH_USER=admin\n'
                    '   - OPENSEARCH_PASSWORD=admin'
                ))
                return
            
            from main.opensearch_docs import reindexar_todo
            reindexar_todo()
            self.stdout.write(self.style.SUCCESS('Indexación en OpenSearch completada exitosamente'))
            
        except ImportError as e:
            self.stdout.write(self.style.ERROR(
                f'Error de importacion: {str(e)}\n'
                'Ejecuta: pip install -r requirements.txt'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error en indexación OpenSearch: {str(e)}'))
            logger.exception('Error durante indexación en OpenSearch')
