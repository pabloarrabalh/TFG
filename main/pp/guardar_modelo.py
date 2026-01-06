"""
GUARDAR MODELO ENTRENADO - VERSIÓN V5
Maneja correctamente roles opcionales (muchos son [])
"""

import pickle
import pandas as pd
import sys
import os
import numpy as np
import json
import re
from pathlib import Path

print("\n" + "="*80)
print("💾 GUARDANDO MODELO ENTRENADO CON ROLES")
print("="*80 + "\n")


def extraer_roles_destacados(df_gk):
    """
    Extrae features de roles para porteros Top 5
    Maneja correctamente roles como listas vacías []
    """
    print("🎯 Extrayendo roles destacados...\n")
    
    roles_features = {
        'rol_pos_porterias_cero': [],
        'rol_val_porterias_cero': [],
        'rol_pos_paradas': [],
        'rol_val_paradas': [],
        'rol_pos_save_pct': [],
        'rol_val_save_pct': [],
    }
    
    # Roles para porteros (los que nos importan)
    roles_portero = ['porterias_cero', 'paradas', 'save_pct']
    
    for idx, row in df_gk.iterrows():
        roles_row = row.get('roles', [])
        
        # Si es string, intentar parsear como dict o lista
        if isinstance(roles_row, str):
            if roles_row.strip() in ['[]', '{}', '']:
                roles_row = {}
            else:
                try:
                    roles_row = eval(roles_row)
                except:
                    roles_row = {}
        
        # Si es lista vacía, convertir a dict vacío
        if isinstance(roles_row, list) and len(roles_row) == 0:
            roles_row = {}
        
        # Si es lista de dicts (puede pasar), convertir a dict único
        if isinstance(roles_row, list) and len(roles_row) > 0:
            # Fusionar todos los dicts de la lista
            roles_dict = {}
            for item in roles_row:
                if isinstance(item, dict):
                    roles_dict.update(item)
            roles_row = roles_dict
        
        # Procesar roles encontrados
        for rol_key in roles_portero:
            pos_key = f"rol_pos_{rol_key}"
            val_key = f"rol_val_{rol_key}"
            
            if rol_key in roles_row and isinstance(roles_row[rol_key], list) and len(roles_row[rol_key]) == 2:
                try:
                    posicion, valor = roles_row[rol_key]
                    roles_features[pos_key].append(posicion if posicion else 0)
                    roles_features[val_key].append(valor if valor else 0)
                except:
                    roles_features[pos_key].append(0)
                    roles_features[val_key].append(0)
            else:
                # Rol no presente o mal formado, llenar con 0
                roles_features[pos_key].append(0)
                roles_features[val_key].append(0)
    
    # Crear DataFrame con features de roles
    df_roles = pd.DataFrame(roles_features)
    
    print(f"✅ Features de roles extraídos: {len(df_roles.columns)}")
    print(f"   Columnas: {list(df_roles.columns)}")
    print(f"   Porteros con al menos 1 rol: {sum(df_roles.max(axis=1) > 0)}\n")
    
    return df_roles


def crear_feature_es_top5(df_gk):
    """
    Crea feature booleana: es Top 5 en algún rol de portero
    Maneja correctamente roles opcionales
    """
    print("⭐ Creando features de Top 5...\n")
    
    is_top5_list = []
    
    for idx, row in df_gk.iterrows():
        roles_row = row.get('roles', [])
        
        # Parsear roles
        if isinstance(roles_row, str):
            if roles_row.strip() in ['[]', '{}', '']:
                roles_row = {}
            else:
                try:
                    roles_row = eval(roles_row)
                except:
                    roles_row = {}
        
        # Si es lista vacía, convertir a dict vacío
        if isinstance(roles_row, list) and len(roles_row) == 0:
            roles_row = {}
        
        # Si es lista de dicts, convertir
        if isinstance(roles_row, list) and len(roles_row) > 0:
            roles_dict = {}
            for item in roles_row:
                if isinstance(item, dict):
                    roles_dict.update(item)
            roles_row = roles_dict
        
        # Verificar si es Top 5
        is_top5 = 0
        
        if isinstance(roles_row, dict):
            for rol_key, rol_data in roles_row.items():
                if isinstance(rol_data, list) and len(rol_data) == 2:
                    pos = rol_data[0]
                    if pos and pos <= 5:
                        is_top5 = 1
                        break
        
        is_top5_list.append(is_top5)
    
    feature_top5 = pd.Series(is_top5_list, name='is_top5_en_algo')
    
    print(f"✅ Top 5 porteros: {sum(is_top5_list)} de {len(is_top5_list)}\n")
    
    return feature_top5


def guardar_modelo_con_roles(
    path_modelo="modelo_porteros.pkl",
    path_features="feature_cols.pkl",
    path_csv="players_with_features_exp3_CORREGIDO.csv"
):
    """
    Guarda modelo entrenado con roles destacados integrados
    Maneja correctamente roles opcionales
    """

    # ============================================================
    # 1. VERIFICAR CSV
    # ============================================================

    if not os.path.exists(path_csv):
        print(f"❌ Error: No se encontró {path_csv}")
        print("\n⚠️ NECESITAS EJECUTAR PRIMERO:")
        print("   $ python completo.py\n")
        return False

    print(f"✅ CSV encontrado: {path_csv}")
    print(f"   Tamaño: {os.path.getsize(path_csv) / 1024 / 1024:.1f} MB\n")

    # ============================================================
    # 2. CARGAR CSV
    # ============================================================

    print("⏳ Cargando datos procesados...\n")

    try:
        from sklearn.ensemble import RandomForestRegressor

        df = pd.read_csv(path_csv)
        print(f"✅ Datos cargados: {df.shape[0]} filas, {df.shape[1]} columnas\n")

        # ============================================================
        # 3. FILTRAR PORTEROS
        # ============================================================

        print("🎯 Filtrando porteros...\n")

        df_gk = df[df["posicion"] == "PT"].copy()
        print(f"✅ Porteros encontrados: {len(df_gk)}")

        df_gk = df_gk[df_gk["puntosFantasy"].between(-10, 30)].copy()
        print(f"✅ Porteros tras filtro: {len(df_gk)}\n")

        # ============================================================
        # 4. EXTRAER FEATURES DE ROLES
        # ============================================================

        df_roles = extraer_roles_destacados(df_gk)
        feature_top5 = crear_feature_es_top5(df_gk)

        # Agregar features de roles al dataframe
        df_gk_con_roles = df_gk.copy()
        for col in df_roles.columns:
            df_gk_con_roles[col] = df_roles[col].values
        df_gk_con_roles["is_top5_en_algo"] = feature_top5.values

        # ============================================================
        # 5. PREPARAR FEATURES NUMÉRICAS
        # ============================================================

        print("📊 Preparando features base...\n")

        meta_cols = [
            "puntosFantasy", "temporada", "jornada", "player", "posicion",
            "Equipo_propio", "Equipo_rival", "fecha_partido", "target_pf_next",
            "Titular", "Min_partido", "Gol_partido", "PSxG", "Goles_en_contra",
            "Porcentaje_paradas", "Amarillas", "Rojas", "rol", "rank_porterias_cero",
            "rank_save_pct", "roles", "home", "away", "Date", "HS", "AS", "HST", "AST",
            "Unnamed: 0"
        ]

        candidate_cols = [col for col in df_gk_con_roles.columns if col not in meta_cols]

        print(f"✅ Candidatas iniciales: {len(candidate_cols)}\n")

        # ============================================================
        # 6. FILTRAR SOLO NUMÉRICAS
        # ============================================================

        print("🔍 Filtrando columnas numéricas...\n")

        numeric_cols = []

        for col in candidate_cols:
            try:
                if df_gk_con_roles[col].dtype in [np.float64, np.int64, np.float32, np.int32]:
                    numeric_cols.append(col)
                elif df_gk_con_roles[col].dtype == "object":
                    test_convert = pd.to_numeric(df_gk_con_roles[col], errors="coerce")
                    if test_convert.notna().sum() / len(df_gk_con_roles) > 0.5:
                        numeric_cols.append(col)
                        df_gk_con_roles[col] = test_convert
            except Exception:
                continue

        feature_cols = numeric_cols

        # 🔴 Quitar conducciones y datos del propio partido (leak)
        LEAK_FEATURES = [
            # conducciones (no te interesan)
            "DistanciaConduccion",
            
            "p_win_propio",
            "p_loss_propio",
            "p_draw_match",
            "p_over25_match",
            "ah_line_match",
            "Despejes",
            "xAG",
            "is_top4_propio",
            "is_top4_rival",
            "is_bottom3_rival",
            "defensa_floja_propia",
            "ataque_top_y_defensa_floja",
            "MetrosAvanzadosConduccion",
            "Conducciones",
            "ConduccionesProgresivas",
            "Pases_Completados_Pct",
            "Pases_Totales",

            # datos del propio partido (solo se conocen después)
            "shots_propio_partido",
            "shots_rival_partido",
            "shots_on_target_propio_partido",
            "shots_on_target_rival_partido",
            "xg_team_partido",
            "xg_rival_partido",
            "xG_partido",

            # otras stats de partido a nivel jugador
            "Asist_partido",
            "Tiros",
            "TiroFallado_partido",
            "TiroPuerta_partido",
            "Entradas",
            "Regates",
            "RegatesCompletados",
            "RegatesFallidos",
            "Duelos",
            "DuelosGanados",
            "DuelosPerdidos",
            "DuelosAereosGanados",
            "DuelosAereosPerdidos",
            "DuelosAereosGanadosPct",
            "Bloqueos",
            "BloqueoTiros",
            "BloqueoPase",
        ]

        feature_cols = [c for c in feature_cols if c not in LEAK_FEATURES]
        print(f"✅ Features numéricas tras quitar leak: {len(feature_cols)}")

        roles_cols_final = [c for c in feature_cols if "rol_" in c or "is_top5" in c]
        print(f"   Incluidas (roles): {roles_cols_final}\n")

        # ============================================================
        # 7. PREPARAR X, y
        # ============================================================

        print("📈 Preparando datos de entrenamiento...\n")

        X = df_gk_con_roles[feature_cols].fillna(0)
        y = df_gk_con_roles["puntosFantasy"]

        if X.isna().any().any():
            print("⚠️ Rellenando NaN restantes...")
            X = X.fillna(0)

        if np.isinf(X.values).any():
            print("⚠️ Reemplazando inf...")
            pd.set_option("future.no_silent_downcasting", True)
            X = X.replace([np.inf, -np.inf], 0)

        print(f"✅ X shape: {X.shape}")
        print(f"✅ y shape: {y.shape}")
        print(f"✅ Sin NaN: {not X.isna().any().any()}")
        print(f"✅ Sin inf: {not np.isinf(X.values).any()}\n")

        # ============================================================
        # 8. ENTRENAR RANDOM FOREST
        # ============================================================

        print("⏳ Entrenando Random Forest (incluyendo roles)...\n")

        modelo = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1,
            verbose=0,
        )

        modelo.fit(X, y)
        print("✅ Modelo entrenado\n")

        # Feature importance de roles
        feature_importance = pd.Series(
            modelo.feature_importances_,
            index=feature_cols,
        ).sort_values(ascending=False)

        roles_cols_imp = [c for c in feature_cols if "rol_" in c or "is_top5" in c]
        if len(roles_cols_imp) > 0:
            roles_importance = feature_importance[roles_cols_imp]

            print("📊 Importancia de features de roles:")
            for col, imp in roles_importance.items():
                print(f"   {col}: {imp:.4f}")
            print()

        # ============================================================
        # 9. GUARDAR ARCHIVOS
        # ============================================================

        print("💾 Guardando archivos...\n")

        with open(path_modelo, "wb") as f:
            pickle.dump(modelo, f)
        print(f"✅ Modelo guardado: {path_modelo}")
        print(f"   Tamaño: {os.path.getsize(path_modelo) / 1024 / 1024:.1f} MB\n")

        with open(path_features, "wb") as f:
            pickle.dump(feature_cols, f)
        print(f"✅ Features guardadas: {path_features}")
        print(f"   Total: {len(feature_cols)} (incluyendo {len(roles_cols_imp)} de roles)\n")

        # ============================================================
        # 10. RESUMEN
        # ============================================================

        print("=" * 80)
        print("✅ PROCESO COMPLETADO")
        print("=" * 80)
        print("Modelo: Random Forest + Roles Destacados")
        print(f"Features base: {len(feature_cols) - len(roles_cols_imp)}")
        print(f"Features de roles: {len(roles_cols_imp)}")
        print(f"Total features: {len(feature_cols)}")
        print(f"Muestras entrenamiento: {len(X)}")
        print("\nArchivos generados:")
        print(f"  ✅ {path_modelo}")
        print(f"  ✅ {path_features}\n")

        print("🚀 Próximo paso:")
        print("   $ python predictor.py\n")

        return True

    except Exception as e:
        print("\n❌ Error durante el entrenamiento:")
        print(f"{type(e).__name__}: {e}\n")
        import traceback

        traceback.print_exc()
        return False


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    success = guardar_modelo_con_roles()
    
    if not success:
        print("\n⚠️ No se pudo completar el proceso.\n")
        sys.exit(1)