import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.views.utils import shield_name
from main.models import Equipo

print("=" * 60)
print("SHIELD NAMES PARA EQUIPOS PROBLEMÁTICOS")
print("=" * 60)

equipos = ['Cádiz', 'Almería', 'Leganés', 'Las Palmas', 'Granada']
for eq_name in equipos:
    shield = shield_name(eq_name)
    print(f"{eq_name:20} -> {shield}")

print("\n" + "=" * 60)
print("VALLADOLID DUPLICADO")
print("=" * 60)
for eq in Equipo.objects.filter(nombre__icontains='vallad'):
    print(f"ID={eq.id:2} | {eq.nombre:20} | shield={shield_name(eq.nombre)}")

print("\n" + "=" * 60)
print("ARCHIVOS DE ESCUDO EXISTENTES")
print("=" * 60)
shields_dir = os.path.join(os.getcwd(), 'static', 'escudos')
if os.path.exists(shields_dir):
    files = sorted([f for f in os.listdir(shields_dir) if f.endswith('.png')])
    for f in files:
        print(f"  {f}")
else:
    print(f"ERROR: {shields_dir} no existe")
