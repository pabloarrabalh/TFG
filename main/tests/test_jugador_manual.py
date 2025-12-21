import unittest

class TestJugadorManual(unittest.TestCase):
    def test_solis_girona(self):
        esperado = {
            'player': 'Solís',  # Solís
            'posicion': 'MC',  # MC
            'Equipo_propio': 'Girona',  # Girona
            'Equipo_rival': 'Rayo Vallecano',  # Rayo Vallecano
            'Titular': '1',  # 1
            'Min_partido': '90',  # 90.0
            'Gol_partido': '0.0',  #  Summary -> Columna:Gls
            'Asist_partido': '0.0',  #  Summary -> Columna:Ast
            'xG_partido': '0.0',  #  Summary -> Columna:xG
            'xA_partido': '0.0',  #  Summary -> Columna:xAG
            'TiroF_partido': '0.0',  #  Summary -> Columna:Sh - Columna:SoT
            'TiroPuerta_partido': '0.0',  #  Summary -> Columna:SoT
            'Pases_Totales': '33',  # 33.0 
            'Pases_Completados_Pct': '90.9',  # 90.9
            'Amarillas': '0.0',  # Miscellaneous Stats (Performance) -> CrdY
            'Rojas': '0.0',  # Miscellaneous Stats (Performance) -> CrdR o bien 2 amarillas lo pone a 1
            'Goles_en_contra': '0',  # Cálculo de la suma de goles del equipo contrario mientras está en el campo, solo defensas y porteros
            'puntosFantasy': '2',  # Scrapping a parte (se coge bien)
            'Tkl_challenge': '1.0',  # Defensive Actions (Challenges)-> Columna:Att
            'Att_challenge': '3',  #  Defensive Actions (Challenges)-> Columna:Att
            'Tkl_pct_challenge': '0',   #  Defensive Actions (Challenges)-> Columna:Tkl%
            'Lost_challenge': '3',  #  Defensive Actions (Challenges)-> Columna:Lost
            'Blocks_total': '0',  # Defensive Actions (Blocks)-> Columna:Blocks
            'Blocks_sh': '0',  #  Defensive Actions (Blocks)-> Columna:Sh
            'Blocks_pass': '0',   #  Defensive Actions (Blocks)-> Columna:Pass
            'Clearances': '1',  #  Defensive Actions (Blocks)-> Columna:Clr
            'TakeOn_att': '4',  #  Possession (Take-ons)-> Columna:Att
            'TakeOn_succ': '2',  #  Possession (Take-ons)-> Columna:Succ
            'TakeOn_tkld': '2',  #  Possession (Take-ons)-> Columna:Tkld 
            'Carries_total': '30',  #  Possession -> Columna:Carries
            'Carries_TotDist': '181',  # Possession -> Columna:TotDist
            'Carries_PrgDist': '56',  # Possession -> Columna:PrgDist
            'Carries_PrgC': '0',  # Possession -> Columna:PrgC
            'Aerial_won': '0',  # Miscellaneous Stats -> Columna:Won
            'Aerial_lost': '2',  # Miscellaneous Stats -> Columna: Lost
            'Aerial_won_pct': '0',  # Miscellaneous Stats -> Columna:Won%
        }
        obtenido = {
            'player': 'Solís',
            'posicion': 'MC',
            'Equipo_propio': 'Girona',
            'Equipo_rival': 'Rayo Vallecano',
            'Titular': 1,
            'Min_partido': 90.0,
            'Gol_partido': 0.0,
            'Asist_partido': 0.0,
            'xG_partido': 0.0,
            'xA_partido': 0.0,
            'TiroF_partido': 0.0,
            'TiroPuerta_partido': 0.0,
            'Pases_Totales': 33.0,
            'Pases_Completados_Pct': 0.0,
            'Amarillas': 0.0,
            'Rojas': 0.0,
            'Goles_en_contra': 0,
            'puntosFantasy': 2,
            'Tkl_challenge': 1.0,
            'Att_challenge': 3.0,
            'Tkl_pct_challenge': 0.0,
            'Lost_challenge': 3.0,
            'Blocks_total': 0.0,
            'Blocks_sh': 0.0,
            'Blocks_pass': 0.0,
            'Clearances': 1.0,
            'TakeOn_att': 4.0,
            'TakeOn_succ': 2.0,
            'TakeOn_tkld': 2.0,
            'Carries_total': 30.0,
            'Carries_TotDist': 181.0,
            'Carries_PrgDist': 56.0,
            'Carries_PrgC': 0.0,
            'Aerial_won': 0.0,
            'Aerial_lost': 2.0,
            'Aerial_won_pct': 0.0,
        }
        def normaliza(v):
            # Trata 0, 0.0, '0', '0.0' como '0'
            if v == 0 or v == 0.0 or v == '0' or v == '0.0':
                return '0'
            if isinstance(v, float) and v.is_integer():
                return str(int(v))
            return str(v)
        obtenido_str = {k: normaliza(v) for k, v in obtenido.items()}
        esperado_str = {k: normaliza(v) for k, v in esperado.items()}
        diferencias = []
        for k in esperado_str:
            if esperado_str[k] != obtenido_str.get(k, None):
                diferencias.append(f"{k}: esperado={esperado_str[k]} | obtenido={obtenido_str.get(k, None)}")
        if diferencias:
            msg = "\nDiferencias encontradas:\n" + "\n".join(diferencias)
            self.fail(msg)

if __name__ == '__main__':
    unittest.main()
