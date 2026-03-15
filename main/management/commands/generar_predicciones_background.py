"""
Genera predicciones pendientes en background sin parar hasta completar todas.
Ejecutar como daemon en el contenedor después del INIT.

Uso: python manage.py generar_predicciones_background --batch 100 --tempo 25_26
      (por defecto corre en modo continuo hasta completar)

O parar antes:
      python manage.py generar_predicciones_background --single  (solo 1 lote)
"""

import logging
import time
from django.core.management.base import BaseCommand
from main.utils.prediction_on_demand import generar_predicciones_pendientes, limpiar_predicciones_generadas

_log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Genera predicciones pendientes en background (continuo hasta completar)'

    def add_arguments(self, parser):
        parser.add_argument('--batch', type=int, default=50, help='Número de predicciones por lote')
        parser.add_argument('--tempo', type=str, default='25_26', help='Temporada (ej: 25_26)')
        parser.add_argument('--cleanup', action='store_true', help='Limpia pedidos ya generados')
        parser.add_argument('--single', action='store_true', help='Solo genera 1 lote y termina (testing)')
        parser.add_argument('--wait', type=int, default=2, help='Segundos entre lotes (default: 2)')

    def handle(self, *args, **options):
        verbosity = int(options.get('verbosity', 1))
        batch_size = options['batch']
        tempo = options['tempo']
        wait_secs = options['wait']
        single_mode = options['single']
        
        # Modo single (testing)
        if single_mode:
            if verbosity >= 1:
                self.stdout.write(f"[BACKGROUND-SINGLE] Generando 1 lote ({tempo})...")
            
            generadas, errores = generar_predicciones_pendientes(
                batch_size=batch_size,
                tempo_name=tempo
            )
            
            if verbosity >= 1:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Generadas: {generadas}  |  ✗ Errores: {errores}"
                    )
                )
            return
        
        # Modo continuo (default) - corre hasta terminar
        if verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[BACKGROUND-CONTINUOUS] Generando predicciones {tempo}..."
                )
            )
            self.stdout.write(f"  Batch: {batch_size}  |  Wait: {wait_secs}s  |  ^C para parar")
        
        lote = 0
        generadas_total = 0
        errores_total = 0
        
        try:
            while True:
                lote += 1
                
                generadas, errores = generar_predicciones_pendientes(
                    batch_size=batch_size,
                    tempo_name=tempo
                )
                
                generadas_total += generadas
                errores_total += errores
                
                # Si no se generó nada, hemos terminado
                if generadas == 0:
                    if verbosity >= 1:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"\n✅ COMPLETADO! Total: {generadas_total} generadas, {errores_total} errores"
                            )
                        )
                    break
                
                if verbosity >= 2:
                    self.stdout.write(
                        f"  [Lote {lote}] ✓ {generadas}  |  ✗ {errores}  |  Total: {generadas_total}"
                    )
                elif verbosity >= 1:
                    self.stdout.write('.', ending='', flush=True)
                
                # Esperar antes del siguiente lote
                time.sleep(wait_secs)
        
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⏸️  Interrumpido en lote {lote}"
                )
            )
            if verbosity >= 1:
                self.stdout.write(f"  Parcial: {generadas_total} generadas, {errores_total} errores")
        
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Error en background: {e}")
            )
        
        # Cleanup opcional
        if options['cleanup']:
            deleted = limpiar_predicciones_generadas()
            if verbosity >= 1:
                self.stdout.write(f"[CLEANUP] Eliminados {deleted} pedidos completados")

