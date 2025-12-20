import pandas as pd
import os
from statsbombpy import sb

# CONFIGURACIÓN
pd.set_option('display.max_columns', None)
if not os.path.exists('data'): os.makedirs('data')

COLUMNAS_MODELO = [
    'player', 'posicion', 'Equipo_propio', 'Equipo_rival', 'Titular', 
    'Min_partido', 'Gol_partido', 'Asist_partido', 'xG_partido', 'xA_partido', 
    'TiroF_partido', 'TiroPuerta_partido', 'Pases_Totales', 'Pases_Completados_Pct', 
    'Amarillas', 'Rojas', 'Tackles_ganados', 'Intercepciones', 'Bloqueos', 
    'Saves', 'SoTA', 'Save_Pct', 'PSxG_partido', 'Goles_en_contra'
]

MAPA_POSICIONES = {
    'Goalkeeper': 'PT',
    'Right Back': 'DF', 'Left Back': 'DF', 'Center Back': 'DF', 
    'Right Center Back': 'DF', 'Left Center Back': 'DF',
    'Right Wing Back': 'DF', 'Left Wing Back': 'DF',
    'Center Defensive Midfield': 'MC', 'Right Defensive Midfield': 'MC', 'Left Defensive Midfield': 'MC',
    'Center Midfield': 'MC', 'Right Center Midfield': 'MC', 'Left Center Midfield': 'MC',
    'Right Midfield': 'MC', 'Left Midfield': 'MC',
    'Center Attacking Midfield': 'MC', 'Right Attacking Midfield': 'MC', 'Left Attacking Midfield': 'MC',
    'Right Wing': 'DT', 'Left Wing': 'DT', 'Center Forward': 'DT', 
    'Secondary Striker': 'DT', 'Left Center Forward': 'DT', 'Right Center Forward': 'DT'
}

def extraer_desde_statsbomb(match_id):
    try:
        print(f"\n>>> CONECTANDO A API STATSBOMB (ID: {match_id}) <<<")
        events = sb.events(match_id=match_id)
        
        # GUARDAR RAW
        events.to_csv(f"data/statsbomb_RAW_{match_id}.csv", index=False, encoding='utf-8-sig')

        # Goles y xG del rival para el portero
        goles_rival = events[(events['type'] == 'Shot') & (events['shot_outcome'] == 'Goal')].groupby('team').size().to_dict()
        xg_rival = events[events['type'] == 'Shot'].groupby('team')['shot_statsbomb_xg'].sum().to_dict()

        # xA Decimal
        tiros = events[events['type'] == 'Shot'].copy()
        dict_xa = tiros.dropna(subset=['shot_key_pass_id']).set_index('shot_key_pass_id')['shot_statsbomb_xg'].to_dict()
        events['xA_valor'] = events['id'].map(dict_xa).fillna(0)

        # Minutos y Alineación
        max_min = events['minute'].max()
        sust_in = events[events['type'] == 'Substitution'].set_index('substitution_replacement')['minute'].to_dict()
        sust_out = events[events['type'] == 'Substitution'].set_index('player')['minute'].to_dict()
        lineups = sb.lineups(match_id=match_id)
        
        player_meta = {}
        eqs = list(lineups.keys())
        for eq in eqs:
            rival = eqs[1] if eq == eqs[0] else eqs[0]
            for _, p in lineups[eq].iterrows():
                player_meta[p['player_name']] = {
                    'pos': MAPA_POSICIONES.get(p['positions'][0]['position'] if p['positions'] else '', 'MC'),
                    'titular': 1 if any(pos['start_reason'] == 'Starting XI' for pos in p['positions']) else 0,
                    'eq': eq, 'rival': rival,
                    'rival_xg': xg_rival.get(rival, 0.0),
                    'goles_recibidos': goles_rival.get(rival, 0)
                }

        df_ev = events[events['player'].notna()].copy()
        final = df_ev.groupby('player').agg(
            Amarillas=('foul_committed_card', lambda x: x.isin(['Yellow Card', 'Second Yellow']).sum()),
            Rojas=('foul_committed_card', lambda x: (x == 'Red Card').sum()),
            Intercepciones=('interception_outcome', lambda x: x.isin(['Success', 'Won']).sum()),
            Bloqueos=('type', lambda x: (x == 'Block').sum()),
            Tackles_ganados=('type', lambda x: (x == 'Ball Recovery').sum()),
            xA_partido=('xA_valor', 'sum')
        )

        tiros_stat = df_ev[df_ev['type'] == 'Shot'].groupby('player').agg(
            Gol_partido=('shot_outcome', lambda x: (x == 'Goal').sum()),
            TiroF_partido=('id', 'count'),
            TiroPuerta_partido=('shot_outcome', lambda x: x.isin(['Goal', 'Saved', 'Post', 'Saved to Post']).sum()),
            xG_partido=('shot_statsbomb_xg', 'sum')
        )

        pases = df_ev[df_ev['type'] == 'Pass'].groupby('player').agg(
            Pases_Totales=('id', 'count'),
            Cmp=('pass_outcome', lambda x: x.isna().sum()),
            Asist_partido=('pass_goal_assist', lambda x: x.fillna(False).sum())
        )
        pases['Pases_Completados_Pct'] = (pases['Cmp'] / pases['Pases_Totales'] * 100).fillna(0)

        porteros = df_ev[df_ev['type'] == 'Goal Keeper'].groupby('player').agg(
            Saves=('goalkeeper_type', lambda x: x.isin(['Saved Only', 'Collected', 'Punch']).sum()),
            SoTA=('goalkeeper_type', lambda x: x.isin(['Saved Only', 'Goal Conceded', 'Collected', 'Punch']).sum())
        )
        porteros['Save_Pct'] = (porteros['Saves'] / porteros['SoTA'] * 100).fillna(0)

        df_res = final.join(tiros_stat, how='left').join(pases, how='left').join(porteros, how='left').fillna(0).reset_index()
        
        df_res['posicion'] = df_res['player'].map(lambda x: player_meta.get(x, {}).get('pos', 'MC'))
        df_res['Equipo_propio'] = df_res['player'].map(lambda x: player_meta.get(x, {}).get('eq', 'N/A'))
        df_res['Equipo_rival'] = df_res['player'].map(lambda x: player_meta.get(x, {}).get('rival', 'N/A'))
        df_res['Titular'] = df_res['player'].map(lambda x: player_meta.get(x, {}).get('titular', 0))
        df_res['Goles_en_contra'] = df_res.apply(lambda r: player_meta.get(r['player'], {}).get('goles_recibidos', 0) if r['posicion'] == 'PT' else 0, axis=1)
        df_res['PSxG_partido'] = df_res.apply(lambda r: player_meta.get(r['player'], {}).get('rival_xg', 0.0) if r['posicion'] == 'PT' else 0.0, axis=1)
        df_res['Min_partido'] = df_res.apply(lambda r: (sust_out.get(r['player'], max_min) - (0 if r['Titular'] else sust_in.get(r['player'], 0))), axis=1)

        return estandarizar(df_res)
    except Exception as e: print(f"Error: {e}"); return None

def estandarizar(df):
    for c in ['Titular', 'Min_partido', 'Gol_partido', 'Asist_partido', 'Pases_Totales', 'Saves', 'SoTA', 'Goles_en_contra']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    for c in ['xG_partido', 'xA_partido', 'Pases_Completados_Pct', 'Save_Pct', 'PSxG_partido']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0).round(2)
    return df[COLUMNAS_MODELO]

if __name__ == "__main__":
    res = extraer_desde_statsbomb(3825848)
    if res is not None: res.to_csv("data/dataset_API_ordenado.csv", index=False)