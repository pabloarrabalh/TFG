from django.core.management.base import BaseCommand
from main.scrapping.popularDB import fase_4_precalcular_percentiles


class Command(BaseCommand):
    help = 'Precalcula la posición y percentiles de todos los jugadores y los guarda en EquipoJugadorTemporada'

    def handle(self, *args, **options):
        self.stdout.write('⏳ Calculando posición y percentiles y guardando en BD...')
        fase_4_precalcular_percentiles()
        self.stdout.write(self.style.SUCCESS('✅ Posición y percentiles guardados en BD correctamente'))

