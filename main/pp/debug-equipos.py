"""
DEBUG: Ver equipos y porteros disponibles en el CSV
"""

import pandas as pd
from pathlib import Path

# Buscar CSV
search_paths = [
    Path.cwd(),
    Path.cwd() / "main" / "pp",
    Path.cwd() / "main",
    Path.cwd() / "data" / "temporada_25_26",
    Path.cwd() / "data",
    Path.cwd().parent,
    Path.cwd().parent / "main" / "pp",
]

csv_path = None
for path in search_paths:
    full_path = path / "players_with_features_exp3_CORREGIDO.csv"
    if full_path.exists():
        csv_path = str(full_path)
        break

if not csv_path:
    print("❌ No se encontró players_with_features_exp3_CORREGIDO.csv")
    exit(1)

print(f"\n📂 Cargando: {csv_path}\n")
df = pd.read_csv(csv_path)

# ============================================================
# EQUIPOS ÚNICOS
# ============================================================

print("="*80)
print("EQUIPOS ÚNICOS EN EL CSV")
print("="*80 + "\n")

equipos = sorted(df["Equipo_propio"].unique())
print(f"Total equipos: {len(equipos)}\n")

for equipo in equipos:
    count = len(df[df["Equipo_propio"] == equipo])
    print(f"  {equipo:30s} ({count} registros)")

# ============================================================
# PORTEROS POR EQUIPO
# ============================================================

print(f"\n{'='*80}")
print("PORTEROS DISPONIBLES POR EQUIPO (JORNADA 18)")
print("="*80 + "\n")

# Filtrar jornada 17 (para J18, usamos datos de J17)
df_j17 = df[(df["temporada"] == "25_26") & (df["jornada"] == 17)].copy()

if len(df_j17) == 0:
    print("⚠️  No hay datos de jornada 17")
    print("Intentando con última jornada disponible...\n")
    jornada_max = df[df["temporada"] == "25_26"]["jornada"].max()
    df_j17 = df[(df["temporada"] == "25_26") & (df["jornada"] == jornada_max)].copy()
    print(f"Usando jornada: {jornada_max}\n")

# Agrupar por equipo
for equipo in sorted(df_j17["Equipo_propio"].unique()):
    porteros = df_j17[df_j17["Equipo_propio"] == equipo]["player"].unique()
    print(f"\n{equipo.upper()}:")
    for portero in sorted(porteros):
        print(f"  - {portero}")

# ============================================================
# BÚSQUEDA FLEXIBLE
# ============================================================

print(f"\n{'='*80}")
print("BÚSQUEDA FLEXIBLE DE EQUIPOS")
print("="*80 + "\n")

# Términos de búsqueda
términos_búsqueda = [
    "rayo", "getafe", "celta", "valencia", "osasuna", "athletic",
    "elche", "villarreal", "espanyol", "barcelona", "sevilla",
    "levante", "mallorca", "girona", "alaves", "oviedo", "real sociedad"
]

for término in términos_búsqueda:
    matches = [e for e in equipos if término.lower() in e.lower()]
    if matches:
        print(f"'{término}' → {matches}")
    else:
        print(f"'{término}' → ❌ NO ENCONTRADO")

print(f"\n{'='*80}\n")
