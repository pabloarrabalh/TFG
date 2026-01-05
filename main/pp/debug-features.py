"""
DEBUG: Ver exactamente qué features tiene el modelo
"""

import pickle
from pathlib import Path

def buscar_archivo(filename):
    search_paths = [
        Path.cwd(),
        Path.cwd() / "main" / "pp",
        Path.cwd() / "main",
        Path.cwd() / "data" / "temporada_25_26",
        Path.cwd() / "data",
        Path.cwd().parent,
        Path.cwd().parent / "main" / "pp",
    ]
    
    for path in search_paths:
        full_path = path / filename
        if full_path.exists():
            return str(full_path)
    return None

# Cargar feature_cols
features_path = buscar_archivo("feature_cols.pkl")
if not features_path:
    print("❌ No se encontró feature_cols.pkl")
    exit(1)

with open(features_path, 'rb') as f:
    feature_cols = pickle.load(f)

print(f"\n{'='*80}")
print(f"FEATURES DEL MODELO: {len(feature_cols)}")
print(f"{'='*80}\n")

for i, col in enumerate(feature_cols, 1):
    print(f"{i:3d}. {col}")

# Agrupar por categoría
print(f"\n{'='*80}")
print("RESUMEN POR CATEGORÍA")
print(f"{'='*80}\n")

categorias = {}
for col in feature_cols:
    if col.startswith("pf_last5"):
        cat = "Rachas Portero - PF"
    elif col.startswith("gc_last5") or col.startswith("clean_last5") or col.startswith("psxg_last5"):
        cat = "Rachas Portero - GC/Clean"
    elif col.startswith("savepct") or col.startswith("psxg_gc_diff"):
        cat = "Rachas Portero - Paradas"
    elif col.startswith("xg_rival") or col.startswith("shots_on_target"):
        cat = "Rachas Equipo - Ataque Rival"
    elif col.startswith("gf_last5") or col.startswith("gc_per90") or col.startswith("goal_diff"):
        cat = "Rachas Equipo - Goles"
    elif col.startswith("p_") and col.endswith("_match"):
        cat = "Cuotas"
    elif col.startswith("rol_") or col.startswith("score_") or col.startswith("elite_") or col.startswith("is_top"):
        cat = "Roles/Élite"
    elif col in ["local", "pts", "gc", "posicion_equipo", "pts_rival", "gc_rival", "posicion_rival"]:
        cat = "Clasificación"
    else:
        cat = "Otros"
    
    if cat not in categorias:
        categorias[cat] = []
    categorias[cat].append(col)

for cat in sorted(categorias.keys()):
    print(f"\n{cat}: {len(categorias[cat])} features")
    for col in sorted(categorias[cat])[:5]:
        print(f"  - {col}")
    if len(categorias[cat]) > 5:
        print(f"  ... y {len(categorias[cat]) - 5} más")

print(f"\n{'='*80}")
