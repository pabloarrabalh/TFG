"""
PREDICTOR V5 - JORNADA 18 COMPLETA (10 PARTIDOS)
Predice los 2 porteros de cada partido
"""

import pickle
import pandas as pd
from pathlib import Path
import sys


# ============================================================
# BUSCAR ARCHIVO EN MÚLTIPLES UBICACIONES
# ============================================================

def buscar_archivo(filename, search_paths=None):
    if search_paths is None:
        search_paths = [
            Path.cwd(),
            Path.cwd() / "main" / "pp",
            Path.cwd() / "main",
            Path.cwd() / "data" / "temporada_25_26",
            Path.cwd() / "data",
            Path.cwd().parent,
            Path.cwd().parent / "main" / "pp",
            Path.cwd().parent / "data" / "temporada_25_26",
        ]
    
    for path in search_paths:
        full_path = path / filename
        if full_path.exists():
            return str(full_path)
    
    return None


# ============================================================
# CARGAR MODELO LIMPIO
# ============================================================
def cargar_modelo():
    print("\n" + "="*80)
    print("🚀 PREDICTOR DE PUNTOS FANTASY - LA LIGA (JORNADA 18 COMPLETA)")
    print("="*80 + "\n")
    
    # ANTES:
    # modelo_path = buscar_archivo("modelo_porteros_limpio.pkl")
    # features_path = buscar_archivo("feature_cols_limpio.pkl")

    # AHORA:
    modelo_path = buscar_archivo("modelo_porteros.pkl")
    if not modelo_path:
        print("❌ Error: No se encontró modelo_porteros.pkl")
        return None, None

    features_path = buscar_archivo("feature_cols.pkl")
    if not features_path:
        print("❌ Error: No se encontró feature_cols.pkl")
        return None, None

    print(f"📂 Cargando modelo desde: {modelo_path}")

    try:
        with open(modelo_path, "rb") as f:
            modelo = pickle.load(f)
        with open(features_path, "rb") as f:
            feature_cols = pickle.load(f)

        print(f"✅ Modelo cargado. {len(feature_cols)} features\n")
        return modelo, feature_cols

    except Exception as e:
        print(f"❌ Error al cargar: {e}\n")
        return None, None


# ============================================================
# IMPORTAR FUNCIÓN DE PREDICCIÓN
# ============================================================

def importar_predictor():
    try:
        from futro import predecir_partido
        return predecir_partido
    except ImportError:
        print("❌ Error: No se puede importar futro.py")
        return None


# ============================================================
# PREDECIR PARTIDOS (AMBOS PORTEROS)
# ============================================================

def predecir_partidos(modelo, feature_cols, jornada=None):
    print("\n" + "="*60)
    if jornada:
        print(f"🎯 PREDICCIONES - JORNADA {jornada} (10 PARTIDOS - 20 PORTEROS)")
    else:
        print("🎯 PREDICCIONES (jornada automática)")
    print("="*60 + "\n")
    
    predecir_partido = importar_predictor()
    if not predecir_partido:
        return []
    
    # ⭐ JORNADA 18 - 10 PARTIDOS COMPLETOS
    # Formato: (partido_formato_futro, [portero_local, portero_visitante])
    partidos = [
        ("rayo-getafe", ["Augusto Batalla", "David Soria"]),
        ("rc celta-valencia cf", ["Ionuț Radu", "Julen Agirrezabala"]),
        ("ca osasuna-athletic", ["Sergio Herrera", "Unai Simón"]),
        ("elche-villarreal", ["Iñaki Peña", "Luiz Lúcio Reis Júnior"]),
        ("rcd espanyol-fc barcelona", ["Marko Dmitrović", "Joan García"]),
        ("sevilla-levante", ["Odysseas Vlachodimos", "Mathew Ryan"]),
        ("real madrid-betis", ["Thibaut Courtois", "Álvaro Vallés"]),
        ("alaves-oviedo", ["Antonio Sivera", "Aarón Escandell"]),
        ("rcd mallorca-girona fc", ["Leo Román", "Paulo Gazzaniga"]),
        ("real sociedad-atletico madrid", ["Álex Remiro", "Jan Oblak"]),
    ]
    
    resultados = []
    
    for partido, porteros in partidos:
        print(f"\n{'='*80}")
        print(f"🏟️  PARTIDO: {partido.upper()}")
        print(f"{'='*80}")
        
        for portero in porteros:
            print(f"\n📊 Prediciendo: {portero}")
            print("-" * 60)
            
            try:
                if jornada:
                    pred = predecir_partido(
                        partido,
                        portero,
                        modelo,
                        feature_cols,
                        jornada=jornada
                    )
                else:
                    pred = predecir_partido(
                        partido,
                        portero,
                        modelo,
                        feature_cols
                    )
                
                if pred.get("error"):
                    print(f"  ❌ Error: {pred['error']}")
                else:
                    print(f"  ✅ Predicción: {pred['prediccion_redondeada']} puntos")
                    print(f"  📈 Raw: {pred['prediccion_raw']:.2f}")
                    print(f"  🏆 Equipo: {pred['equipo_portero'].upper()}")
                    print(f"  🏠 Posición: {'LOCAL' if pred['es_local'] else 'VISITANTE'}")
                    
                    ctx = pred["contexto"]
                    pf5 = ctx.get("pf_last5_mean")
                    if pf5 is not None:
                        print(f"  - PF últimos 5: {pf5:.2f}")
                    else:
                        print("  - PF últimos 5: -")

                    pos_prop = ctx.get("posicion_propia")
                    pos_riv = ctx.get("posicion_rival")
                    pwin = ctx.get("p_win")

                    print(f"      - Posición propia: {pos_prop if pos_prop is not None else '-'}")
                    print(f"      - Posición rival: {pos_riv if pos_riv is not None else '-'}")
                    if pwin is not None:
                        print(f"      - P(Victoria): {pwin:.0%}")
                    else:
                        print("      - P(Victoria): -")

                    resultados.append(pred)
            
            except Exception as e:
                print(f"  ❌ Error: {str(e)}")
    
    return resultados


# ============================================================
# TABLA RESUMEN POR PARTIDO
# ============================================================

def mostrar_tabla_por_partido(resultados):
    if not resultados:
        print("\n⚠️ No hay resultados para mostrar")
        return
    
    print("\n" + "="*160)
    print("📋 TABLA RESUMEN - JORNADA 18 (20 PORTEROS)")
    print("="*160 + "\n")
    
    df_resumen = pd.DataFrame([
        {
            'Partido': r['partido'].upper(),
            'Portero': r['portero'],
            'Pos': 'L' if r['es_local'] else 'V',
            'Pred': r['prediccion_redondeada'],
            'Raw': f"{r['prediccion_raw']:.2f}",
            **(
                lambda ctx: {
                    'PF5': f"{ctx.get('pf_last5_mean'):.1f}" if ctx.get('pf_last5_mean') is not None else "-",
                    'PosProp': ctx.get('posicion_propia') if ctx.get('posicion_propia') is not None else "-",
                    'PosRiv': ctx.get('posicion_rival') if ctx.get('posicion_rival') is not None else "-",
                    'PWin': f"{ctx.get('p_win'):.0%}" if ctx.get('p_win') is not None else "-",
                }
            )(r['contexto'])
        }
        for r in resultados
    ])
    
    print(df_resumen.to_string(index=False))
    print("\n" + "="*160)

# ============================================================
# TABLA COMPARATIVA
# ============================================================

def mostrar_tabla_comparativa(resultados):
    if not resultados:
        return
    
    print("\n" + "="*160)
    print("⚖️  COMPARATIVA: LOCAL vs VISITANTE (10 PARTIDOS)")
    print("="*160 + "\n")
    
    partidos_dict = {}
    for r in resultados:
        partido = r['partido']
        if partido not in partidos_dict:
            partidos_dict[partido] = {}
        
        posicion = 'LOCAL' if r['es_local'] else 'VISIT'
        partidos_dict[partido][posicion] = r
    
    comparativa = []
    for partido, porteros in sorted(partidos_dict.items()):
        if 'LOCAL' in porteros and 'VISIT' in porteros:
            local = porteros['LOCAL']
            visit = porteros['VISIT']
            
            comparativa.append({
                'Partido': partido.upper(),
                'Portero Local': local['portero'],
                'Pred L': local['prediccion_redondeada'],
                'vs': '  VS  ',
                'Portero Visit': visit['portero'],
                'Pred V': visit['prediccion_redondeada'],
                'Dif': local['prediccion_redondeada'] - visit['prediccion_redondeada']
            })
    
    if comparativa:
        df_comp = pd.DataFrame(comparativa)
        print(df_comp.to_string(index=False))
        print("\n" + "="*160)


# ============================================================
# TOP PREDICCIONES
# ============================================================

def mostrar_top_predicciones(resultados):
    if not resultados:
        return
    
    print("\n" + "="*80)
    print("🏆 TOP 5 PORTEROS (PUNTOS ESPERADOS)")
    print("="*80 + "\n")
    
    top5 = sorted(resultados, key=lambda x: x['prediccion_redondeada'], reverse=True)[:5]
    
    for i, r in enumerate(top5, 1):
        print(f"{i}. {r['portero']:25s} ({r['equipo_portero'].upper():20s}) - {r['prediccion_redondeada']} pts")
    
    print("\n" + "="*80)
    print("⚠️  BAJO RIESGO (PUNTOS ESPERADOS)")
    print("="*80 + "\n")
    
    bottom5 = sorted(resultados, key=lambda x: x['prediccion_redondeada'])[:5]
    
    for i, r in enumerate(bottom5, 1):
        print(f"{i}. {r['portero']:25s} ({r['equipo_portero'].upper():20s}) - {r['prediccion_redondeada']} pts")
    
    print("\n" + "="*80)


# ============================================================
# GUARDAR RESULTADOS
# ============================================================

def guardar_resultados_csv(resultados, filename="predicciones_j18_completa.csv"):
    if not resultados:
        print("\n⚠️ No hay resultados para guardar")
        return
    
    filas = []
    for r in resultados:
        ctx = r['contexto']
        pf5 = ctx.get('pf_last5_mean')
        pos_prop = ctx.get('posicion_propia')
        pos_riv = ctx.get('posicion_rival')
        pwin = ctx.get('p_win')
        
        filas.append({
            'Partido': r['partido'],
            'Portero': r['portero'],
            'Equipo': r['equipo_portero'],
            'Posición': 'LOCAL' if r['es_local'] else 'VISITANTE',
            'Jornada': r['jornada'],
            'Predicción': r['prediccion_redondeada'],
            'Raw': round(r['prediccion_raw'], 2),
            'PF_Última5': round(pf5, 2) if pf5 is not None else None,
            'Posición_Propia': pos_prop,
            'Posición_Rival': pos_riv,
            'P_Win': round(pwin, 3) if pwin is not None else None,
        })
    
    df_resultados = pd.DataFrame(filas)
    df_resultados.to_csv(filename, index=False)
    print(f"\n✅ Resultados guardados en: {filename}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    
    modelo, feature_cols = cargar_modelo()
    
    if modelo is None:
        exit(1)
    
    jornada_a_predecir = 18
    
    resultados = predecir_partidos(modelo, feature_cols, jornada=jornada_a_predecir)
    
    mostrar_tabla_por_partido(resultados)
    mostrar_tabla_comparativa(resultados)
    mostrar_top_predicciones(resultados)
    
    guardar_resultados_csv(resultados)
    
    print("\n✅ Ejecución completada")
    print(f"\nTotal predicciones: {len(resultados)}/20")
    print(f"Para cambiar jornada: edita 'jornada_a_predecir = 18'")
    print(f"Para cambiar partidos: edita la lista 'partidos = [...]'\n")