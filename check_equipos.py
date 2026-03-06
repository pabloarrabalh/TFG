import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import Equipo, EquipoJugadorTemporada, Temporada

# Equipos problemáticos
equipos_check = ['Cádiz', 'Almería', 'Leganés', 'Las Palmas', 'Granada']
temp_25_26 = Temporada.objects.get(nombre='25_26')

print("Equipos en 25_26:")
for eq_name in equipos_check:
    eq = Equipo.objects.get(nombre=eq_name)
    count = EquipoJugadorTemporada.objects.filter(equipo=eq, temporada=temp_25_26).count()
    print(f"  {eq_name}: {count} jugadores")

# Checar dónde aparecen estos equipos
print("\nOtras temporadas para estos equipos:")
for eq_name in equipos_check:
    eq = Equipo.objects.get(nombre=eq_name)
    temps = EquipoJugadorTemporada.objects.filter(equipo=eq).values_list('temporada__nombre', flat=True).distinct()
    print(f"  {eq_name}: {list(temps)}")

print("\nTemporadas disponibles:")
for t in Temporada.objects.order_by('-nombre'):
    print(f"  - {t.nombre} (id={t.id})")
