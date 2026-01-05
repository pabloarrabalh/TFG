"""
MODELO PREDICTIVO DE PUNTOS FANTASY - PORTEROS
Versión corregida: SOLO usa features disponibles ANTES del partido

CAMBIOS CLAVE:
1. La clasificación se obtiene de la jornada ANTERIOR (N-1) al partido a predecir
2. Las rachas de equipos se calculan hasta la jornada ANTERIOR
3. Las cuotas SÍ están disponibles antes del partido
4. NO se usan features del partido actual (xg_rival, shots_rival, etc.)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# DICCIONARIO DE NORMALIZACIÓN DE EQUIPOS
# ============================================================================
EQUIV_EQUIPOS = {
    "las palmas": "las palmas", "ud las palmas": "las palmas",
    "athletic": "athletic", "ath bilbao": "athletic", "athletic club": "athletic",
    "atletico madrid": "atletico madrid", "ath madrid": "atletico madrid", "atl madrid": "atletico madrid",
    "barcelona": "barcelona", "fc barcelona": "barcelona",
    "real madrid": "real madrid", "rm": "real madrid",
    "real sociedad": "real sociedad", "sociedad": "real sociedad",
    "rayo vallecano": "rayo vallecano", "rayo": "rayo vallecano", "vallecano": "rayo vallecano",
    "valencia": "valencia", "valencia cf": "valencia",
    "mallorca": "mallorca", "rcd mallorca": "mallorca",
    "celta": "celta", "rc celta": "celta",
    "cadiz": "cadiz", "cadiz cf": "cadiz",
    "girona": "girona", "girona fc": "girona",
    "granada": "granada", "granada cf": "granada",
    "osasuna": "osasuna", "ca osasuna": "osasuna",
    "almeria": "almeria", "ud almeria": "almeria",
    "villarreal": "villarreal", "villarreal cf": "villarreal",
    "getafe": "getafe", "getafe cf": "getafe",
    "betis": "betis", "real betis": "betis",
    "espanyol": "espanyol", "rcd espanyol": "espanyol", "espanol": "espanyol",
    "leganes": "leganes", "cd leganes": "leganes",
    "valladolid": "valladolid", "real valladolid": "valladolid",
    "oviedo": "oviedo", "sevilla": "sevilla", "levante": "levante",
    "elche": "elche", "alaves": "alaves",
}

def normalizar_equipo_series(s: pd.Series) -> pd.Series:
    """Normaliza nombres de equipos en una Serie de pandas"""
    s = s.str.lower().str.strip()
    return s.replace(EQUIV_EQUIPOS)


# ============================================================================
# FUNCIÓN 1: CONSTRUIR CLASIFICACIÓN HISTÓRICA
# ============================================================================
def build_historical_standings(df_partidos: pd.DataFrame) -> pd.DataFrame:
    """
    Construye la clasificación acumulada hasta cada jornada

    IMPORTANTE: Para predecir jornada N, usaremos clasificación de jornada N-1

    Args:
        df_partidos: DataFrame con columnas player, temporada, jornada, 
                     Equipo_propio, Equipo_rival, fecha_partido, local,
                     goles a favor/contra del EQUIPO en ese partido

    Returns:
        DataFrame con clasificación histórica por (temporada, jornada, equipo)
    """
    # Agrupar por equipo y partido para obtener resultados de equipos
    resultados = []

    for (temp, jor, fecha, eq_local, eq_visit), group in df_partidos.groupby(
        ['temporada', 'jornada', 'fecha_partido', 'Equipo_local', 'Equipo_visitante']
    ):
        # Obtener goles del partido
        goles_local = group[group['Equipo_propio'] == eq_local]['Gol_partido'].sum()
        goles_visit = group[group['Equipo_propio'] == eq_visit]['Gol_partido'].sum()

        resultados.append({
            'temporada': temp,
            'jornada': jor,
            'fecha': fecha,
            'equipo_local': eq_local,
            'equipo_visitante': eq_visit,
            'goles_local': goles_local,
            'goles_visitante': goles_visit
        })

    df_res = pd.DataFrame(resultados)

    # Calcular clasificación acumulada
    clasificacion = []

    for temp in df_res['temporada'].unique():
        df_temp = df_res[df_res['temporada'] == temp].sort_values(['jornada', 'fecha'])

        # Obtener todos los equipos de la temporada
        equipos = set(df_temp['equipo_local'].unique()) | set(df_temp['equipo_visitante'].unique())

        # Inicializar stats por equipo
        stats = {eq: {'pj': 0, 'pg': 0, 'pe': 0, 'pp': 0, 'gf': 0, 'gc': 0, 'pts': 0} 
                 for eq in equipos}

        for jor in sorted(df_temp['jornada'].unique()):
            partidos_jor = df_temp[df_temp['jornada'] == jor]

            # Actualizar stats con partidos de esta jornada
            for _, partido in partidos_jor.iterrows():
                local = partido['equipo_local']
                visit = partido['equipo_visitante']
                gl = partido['goles_local']
                gv = partido['goles_visitante']

                # Actualizar local
                stats[local]['pj'] += 1
                stats[local]['gf'] += gl
                stats[local]['gc'] += gv

                # Actualizar visitante
                stats[visit]['pj'] += 1
                stats[visit]['gf'] += gv
                stats[visit]['gc'] += gl

                # Puntos
                if gl > gv:
                    stats[local]['pg'] += 1
                    stats[local]['pts'] += 3
                    stats[visit]['pp'] += 1
                elif gl < gv:
                    stats[visit]['pg'] += 1
                    stats[visit]['pts'] += 3
                    stats[local]['pp'] += 1
                else:
                    stats[local]['pe'] += 1
                    stats[visit]['pe'] += 1
                    stats[local]['pts'] += 1
                    stats[visit]['pts'] += 1

            # Guardar clasificación DESPUÉS de esta jornada
            for equipo, st in stats.items():
                clasificacion.append({
                    'temporada': temp,
                    'jornada': jor,
                    'equipo': equipo,
                    'pj': st['pj'],
                    'pg': st['pg'],
                    'pe': st['pe'],
                    'pp': st['pp'],
                    'gf': st['gf'],
                    'gc': st['gc'],
                    'dg': st['gf'] - st['gc'],
                    'pts': st['pts']
                })

    df_clas = pd.DataFrame(clasificacion)

    # Calcular posición en cada jornada
    df_clas['posicion'] = df_clas.groupby(['temporada', 'jornada'])['pts'].rank(
        method='min', ascending=False
    )

    return df_clas


# ============================================================================
# FUNCIÓN 2: CARGAR Y PREPARAR DATOS DE ODDS
# ============================================================================
def load_and_prepare_odds(path: str, temporada_tag: str) -> pd.DataFrame:
    """
    Carga y prepara datos de cuotas de apuestas

    IMPORTANTE: Las cuotas SÍ están disponibles ANTES del partido
    """
    odds = pd.read_csv(path)
    odds['temporada'] = temporada_tag
    odds['Date'] = pd.to_datetime(odds['Date'], format="%d/%m/%Y", errors="coerce")
    odds['HomeTeam'] = normalizar_equipo_series(odds['HomeTeam'])
    odds['AwayTeam'] = normalizar_equipo_series(odds['AwayTeam'])

    # Calcular probabilidades implícitas
    for c in ['AvgH', 'AvgD', 'AvgA', 'Avg>2.5', 'Avg<2.5']:
        odds[c] = pd.to_numeric(odds[c], errors='coerce')

    odds['inv_H'] = 1 / odds['AvgH']
    odds['inv_D'] = 1 / odds['AvgD']
    odds['inv_A'] = 1 / odds['AvgA']
    odds['sum_inv'] = odds[['inv_H', 'inv_D', 'inv_A']].sum(axis=1)

    odds['p_home'] = odds['inv_H'] / odds['sum_inv']
    odds['p_draw'] = odds['inv_D'] / odds['sum_inv']
    odds['p_away'] = odds['inv_A'] / odds['sum_inv']

    odds['inv_over'] = 1 / odds['Avg>2.5']
    odds['inv_under'] = 1 / odds['Avg<2.5']
    odds['sum_ou'] = odds['inv_over'] + odds['inv_under']
    odds['p_over25'] = odds['inv_over'] / odds['sum_ou']

    odds['ah_line'] = pd.to_numeric(odds['AHh'], errors='coerce')

    # Tiros HISTÓRICOS (del partido jugado - solo para entrenamiento)
    odds['HS'] = pd.to_numeric(odds['HS'], errors='coerce')
    odds['AS'] = pd.to_numeric(odds['AS'], errors='coerce')
    odds['HST'] = pd.to_numeric(odds['HST'], errors='coerce')
    odds['AST'] = pd.to_numeric(odds['AST'], errors='coerce')

    return odds[['temporada', 'Date', 'HomeTeam', 'AwayTeam', 
                 'p_home', 'p_draw', 'p_away', 'p_over25', 'ah_line',
                 'HS', 'AS', 'HST', 'AST']]


# ============================================================================
# FUNCIÓN 3: CONSTRUIR FEATURES PARA ENTRENAMIENTO
# ============================================================================
def build_features_for_training(
    df_players: pd.DataFrame,
    df_standings: pd.DataFrame,
    df_odds: pd.DataFrame
) -> pd.DataFrame:
    """
    Construye features para entrenar el modelo

    CLAVE: Usa clasificación de jornada N-1 para predecir jornada N
    """
    df = df_players.copy()
    df = df.sort_values(['player', 'temporada', 'jornada', 'fecha_partido'])

    # ========================================================================
    # 1. MERGE CON CLASIFICACIÓN DE JORNADA ANTERIOR
    # ========================================================================
    # Para cada partido en jornada N, buscar clasificación de jornada N-1
    df['jornada_anterior'] = df['jornada'] - 1

    # Clasificación equipo propio (jornada anterior)
    df = df.merge(
        df_standings.rename(columns={'equipo': 'Equipo_propio', 'jornada': 'jornada_anterior'}),
        on=['temporada', 'jornada_anterior', 'Equipo_propio'],
        how='left',
        suffixes=('', '_equipo')
    )

    # Clasificación equipo rival (jornada anterior)
    df = df.merge(
        df_standings.rename(columns={'equipo': 'Equipo_rival', 'jornada': 'jornada_anterior'}),
        on=['temporada', 'jornada_anterior', 'Equipo_rival'],
        how='left',
        suffixes=('', '_rival')
    )

    # ========================================================================
    # 2. MERGE CON ODDS (disponibles antes del partido)
    # ========================================================================
    # Intentar merge como local
    df = df.merge(
        df_odds,
        left_on=['temporada', 'Equipo_propio', 'Equipo_rival'],
        right_on=['temporada', 'HomeTeam', 'AwayTeam'],
        how='left'
    )

    # Intentar merge como visitante (donde falló el anterior)
    df_away = df[df['p_home'].isna()].drop(columns=['p_home', 'p_draw', 'p_away', 
                                                      'p_over25', 'ah_line', 'HS', 'AS',
                                                      'HST', 'AST', 'HomeTeam', 'AwayTeam', 'Date'])
    df_away = df_away.merge(
        df_odds,
        left_on=['temporada', 'Equipo_propio', 'Equipo_rival'],
        right_on=['temporada', 'AwayTeam', 'HomeTeam'],
        how='left'
    )

    # Combinar
    df.loc[df['p_home'].isna(), ['p_home', 'p_draw', 'p_away', 'p_over25', 'ah_line',
                                  'HS', 'AS', 'HST', 'AST']] = df_away[
        ['p_home', 'p_draw', 'p_away', 'p_over25', 'ah_line', 'HS', 'AS', 'HST', 'AST']
    ].values

    # ========================================================================
    # 3. CREAR FEATURES DE APUESTAS
    # ========================================================================
    df['p_win_propio'] = df['p_home'] * df['local'] + df['p_away'] * (1 - df['local'])
    df['p_loss_propio'] = df['p_away'] * df['local'] + df['p_home'] * (1 - df['local'])
    df['p_draw_match'] = df['p_draw']
    df['p_over25_match'] = df['p_over25']
    df['ah_line_match'] = df['ah_line']

    # ========================================================================
    # 4. CALCULAR RACHAS DE EQUIPOS (últimos 5 partidos)
    # ========================================================================
    # IMPORTANTE: Estas rachas se calculan con datos HISTÓRICOS

    # Primero necesitamos tiros históricos por equipo y jornada
    # (Estos datos vienen de partidos YA JUGADOS)

    # Agrupar tiros por equipo/jornada
    team_shots = df.groupby(['temporada', 'jornada', 'Equipo_propio']).agg({
        'HS': 'first',  # Tiros cuando juega en casa
        'AS': 'first',  # Tiros cuando juega fuera
        'HST': 'first',
        'AST': 'first'
    }).reset_index()

    # Para cada equipo, calcular sus tiros (ajustando por local/visitante)
    df['shots_team'] = np.where(df['local'] == 1, df['HS'], df['AS'])
    df['shots_on_target_team'] = np.where(df['local'] == 1, df['HST'], df['AST'])

    # Rachas de equipos
    g_team = df.groupby(['Equipo_propio', 'temporada'])

    df['gf_last5_mean_team'] = g_team['gf'].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df['gc_last5_mean_team'] = g_team['gc'].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )

    # Rachas de rivales
    g_rival = df.groupby(['Equipo_rival', 'temporada'])

    df['gf_last5_mean_rival'] = g_rival['gf_rival'].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )
    df['gc_last5_mean_rival'] = g_rival['gc_rival'].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean()
    )

    # ========================================================================
    # 5. TARGET: Puntos fantasy del SIGUIENTE partido
    # ========================================================================
    df['target_pf_next'] = df.groupby(['player', 'temporada'])['puntosFantasy'].shift(-1)

    return df


# ============================================================================
# FUNCIÓN 4: PREDECIR PARTIDO FUTURO
# ============================================================================
def predict_future_match(
    player_name: str,
    equipo_propio: str,
    equipo_rival: str,
    es_local: int,
    temporada: str,
    jornada_a_predecir: int,
    df_historical: pd.DataFrame,
    df_standings: pd.DataFrame,
    df_odds: pd.DataFrame,
    model,
    feature_cols: list
) -> dict:
    """
    Predice puntos fantasy para un partido futuro

    Args:
        player_name: Nombre del jugador
        equipo_propio: Equipo del jugador (normalizado)
        equipo_rival: Equipo rival (normalizado)
        es_local: 1 si juega en casa, 0 si fuera
        temporada: '25_26', etc.
        jornada_a_predecir: Número de jornada a predecir
        df_historical: DataFrame con partidos históricos del jugador
        df_standings: DataFrame con clasificación histórica
        df_odds: DataFrame con cuotas (debe incluir el partido futuro)
        model: Modelo entrenado
        feature_cols: Lista de features que usa el modelo

    Returns:
        Diccionario con la predicción y features usadas
    """
    # Normalizar equipos
    equipo_propio = equipo_propio.lower().strip()
    equipo_rival = equipo_rival.lower().strip()
    equipo_propio = EQUIV_EQUIPOS.get(equipo_propio, equipo_propio)
    equipo_rival = EQUIV_EQUIPOS.get(equipo_rival, equipo_rival)

    # 1. Obtener historial del jugador
    df_player = df_historical[df_historical['player'] == player_name].copy()
    df_player = df_player.sort_values(['temporada', 'jornada', 'fecha_partido'])

    if len(df_player) == 0:
        return {'error': f'Jugador {player_name} no encontrado en histórico'}

    # 2. Calcular rachas del jugador (últimos 5 partidos)
    df_player['pf_last5_mean'] = df_player['puntosFantasy'].rolling(5, min_periods=1).mean()
    df_player['min_last5_mean'] = df_player['Min_partido'].rolling(5, min_periods=1).mean()
    df_player['gc_last5_mean'] = df_player['Goles_en_contra'].rolling(5, min_periods=1).mean()
    df_player['psxg_last5_mean'] = df_player['PSxG'].rolling(5, min_periods=1).mean()
    df_player['savepct_last5_mean'] = df_player['Porcentaje_paradas'].rolling(5, min_periods=1).mean()

    # Tomar valores de rachas del último partido jugado
    last_match = df_player.iloc[-1]

    # 3. Obtener clasificación de jornada anterior
    jornada_clasificacion = jornada_a_predecir - 1

    clas_propio = df_standings[
        (df_standings['temporada'] == temporada) &
        (df_standings['jornada'] == jornada_clasificacion) &
        (df_standings['equipo'] == equipo_propio)
    ]

    clas_rival = df_standings[
        (df_standings['temporada'] == temporada) &
        (df_standings['jornada'] == jornada_clasificacion) &
        (df_standings['equipo'] == equipo_rival)
    ]

    if len(clas_propio) == 0 or len(clas_rival) == 0:
        return {'error': 'Clasificación no encontrada para alguno de los equipos'}

    clas_propio = clas_propio.iloc[0]
    clas_rival = clas_rival.iloc[0]

    # 4. Obtener cuotas del partido futuro
    odds_match = df_odds[
        (df_odds['temporada'] == temporada) &
        (
            ((df_odds['HomeTeam'] == equipo_propio) & (df_odds['AwayTeam'] == equipo_rival)) |
            ((df_odds['HomeTeam'] == equipo_rival) & (df_odds['AwayTeam'] == equipo_propio))
        )
    ]

    if len(odds_match) == 0:
        return {'error': 'Cuotas no encontradas para este partido'}

    odds_match = odds_match.iloc[0]

    # 5. Construir vector de features
    features = {}

    # Rachas del jugador
    features['pf_last5_mean'] = last_match['pf_last5_mean']
    features['min_last5_mean'] = last_match['min_last5_mean']
    features['gc_last5_mean'] = last_match['gc_last5_mean']
    features['psxg_last5_mean'] = last_match['psxg_last5_mean']
    features['savepct_last5_mean'] = last_match['savepct_last5_mean']

    # Clasificación equipo propio
    features['pts'] = clas_propio['pts']
    features['gf'] = clas_propio['gf']
    features['gc'] = clas_propio['gc']
    features['posicion_equipo'] = clas_propio['posicion']

    # Clasificación equipo rival
    features['pts_rival'] = clas_rival['pts']
    features['gf_rival'] = clas_rival['gf']
    features['gc_rival'] = clas_rival['gc']
    features['posicion_rival'] = clas_rival['posicion']

    # Diferencias
    features['pts_diff'] = features['pts'] - features['pts_rival']
    features['gf_diff'] = features['gf'] - features['gf_rival']
    features['gc_diff'] = features['gc'] - features['gc_rival']

    # Flags posición
    features['is_top4_propio'] = int(features['posicion_equipo'] <= 4)
    features['is_top4_rival'] = int(features['posicion_rival'] <= 4)
    features['is_bottom3_rival'] = int(features['posicion_rival'] >= 18)

    # Cuotas
    if es_local:
        features['p_win_propio'] = odds_match['p_home']
        features['p_loss_propio'] = odds_match['p_away']
    else:
        features['p_win_propio'] = odds_match['p_away']
        features['p_loss_propio'] = odds_match['p_home']

    features['p_draw_match'] = odds_match['p_draw']
    features['p_over25_match'] = odds_match['p_over25']
    features['ah_line_match'] = odds_match['ah_line']
    features['local'] = es_local

    # TODO: Calcular rachas de equipos con datos históricos
    # Por ahora las dejamos en 0 o aproximaciones
    features['gf_last5_mean_team'] = clas_propio['gf'] / max(clas_propio['pj'], 1)
    features['gc_last5_mean_team'] = clas_propio['gc'] / max(clas_propio['pj'], 1)
    features['gf_last5_mean_rival'] = clas_rival['gf'] / max(clas_rival['pj'], 1)
    features['gc_last5_mean_rival'] = clas_rival['gc'] / max(clas_rival['pj'], 1)

    # 6. Crear DataFrame con las features en el orden correcto
    X_pred = pd.DataFrame([features])

    # Asegurar que tenemos todas las features necesarias
    for col in feature_cols:
        if col not in X_pred.columns:
            X_pred[col] = 0.0

    X_pred = X_pred[feature_cols]

    # 7. Hacer predicción
    pred = model.predict(X_pred)[0]
    pred_rounded = round(pred)

    return {
        'player': player_name,
        'equipo_propio': equipo_propio,
        'equipo_rival': equipo_rival,
        'jornada': jornada_a_predecir,
        'prediccion': pred,
        'prediccion_redondeada': pred_rounded,
        'features_usadas': features
    }


# ============================================================================
# FUNCIÓN MAIN: EJEMPLO DE USO
# ============================================================================
if __name__ == "__main__":
    print("="*80)
    print("MODELO PREDICTIVO CORREG IDO - SOLO USA DATOS DISPONIBLES ANTES DEL PARTIDO")
    print("="*80)

    # Aquí irían las llamadas a las funciones para:
    # 1. Cargar datos históricos
    # 2. Construir clasificación histórica
    # 3. Cargar odds
    # 4. Construir features
    # 5. Entrenar modelo
    # 6. Predecir partidos futuros

    print("\nFunciones implementadas:")
    print("  ✓ build_historical_standings()")
    print("  ✓ load_and_prepare_odds()")
    print("  ✓ build_features_for_training()")
    print("  ✓ predict_future_match()")