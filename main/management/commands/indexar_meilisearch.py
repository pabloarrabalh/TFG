from django.core.management.base import BaseCommand
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Indexa todos los jugadores y equipos en Meilisearch'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando indexación...'))

        try:
            from main.meilisearch_docs import MEILISEARCH_AVAILABLE

            if not MEILISEARCH_AVAILABLE:
                self.stdout.write(self.style.ERROR(
                    'Meilisearch no esta disponible\n'
                    'Asegúrate de:\n'
                    '1. Tener Meilisearch corriendo en localhost:7700\n'
                    '2. Configurar variables de entorno en .env:\n'
                    '   - MEILISEARCH_HOST=http://localhost:7700\n'
                    '   - MEILISEARCH_API_KEY=<tu_api_key>'
                ))
                return

            from main.meilisearch_docs import reindexar_todo
            reindexar_todo()
            self.stdout.write(self.style.SUCCESS('Indexación en Meilisearch completada exitosamente'))

        except ImportError as e:
            self.stdout.write(self.style.ERROR(
                f'Error de importacion: {str(e)}\n'
                'Ejecuta: pip install -r requirements.txt'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error en indexación Meilisearch: {str(e)}'))
            logger.exception('Error durante indexación en Meilisearch')
