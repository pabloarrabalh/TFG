import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'

    def ready(self):
        """Se ejecuta al iniciar Django"""
        import os
        import threading

        # Importar signals para autoindexación
        try:
            import main.signals  # noqa: F401
        except ImportError:
            pass

        # Solo ejecutar si no es en migraciones
        if 'migrate' not in os.sys.argv and 'makemigrations' not in os.sys.argv:
            init_thread = threading.Thread(target=self._initialize_data, daemon=True)
            init_thread.start()

    def _initialize_data(self):
        """Inicializa datos en background (sin prints de debug)."""
        import time
        time.sleep(2)

        try:
            # ── Roles: solo cargar si faltan ──
            from main.models import EstadisticasPartidoJugador
            sin_roles = EstadisticasPartidoJugador.objects.filter(roles=[]).count()
            total = EstadisticasPartidoJugador.objects.count()
            if total > 0 and sin_roles / total > 0.5:
                from main.scrapping.popularDB import fase_2_cargar_roles
                fase_2_cargar_roles()

            # ── Elasticsearch: solo si disponible ──
            try:
                from main.elasticsearch_docs import reindexar_todo, ELASTICSEARCH_AVAILABLE
                if ELASTICSEARCH_AVAILABLE:
                    reindexar_todo()
            except Exception:
                pass

            # ── Predicciones: generar solo jornadas sin predicciones ──
            self._generar_predicciones_pendientes()

        except Exception as e:
            logger.error("Error durante inicialización: %s", e)

    @staticmethod
    def _generar_predicciones_pendientes():
        """Genera predicciones solo para jornadas de 25/26 que no tengan ninguna."""
        from main.models import Temporada, Jornada, PrediccionJugador
        from django.core.management import call_command

        temporada = Temporada.objects.filter(nombre='25_26').first()
        if not temporada:
            return

        jornadas_sin = (
            Jornada.objects.filter(temporada=temporada)
            .exclude(predicciones_jugadores__isnull=False)
            .order_by('numero_jornada')
        )

        # Optimización: si ya hay predicciones para todas, salir rápido
        if not jornadas_sin.exists():
            return

        for jornada in jornadas_sin:
            if PrediccionJugador.objects.filter(jornada=jornada).exists():
                continue
            try:
                call_command(
                    'generar_predicciones',
                    temporada='25_26',
                    jornada=jornada.numero_jornada,
                    workers=4,
                    verbosity=0,
                )
            except Exception:
                pass
