import psycopg2
import pandas as pd

CSV_PATH = r"data\temporada_25_26\clasificacion_temporada.csv"

def crear_y_poblar_bd_clasificicion(csv_path):
    # Leer CSV
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    # Conectar a Postgres con usuario user1
    conn = psycopg2.connect(
        dbname="laliga",
        user="user1",
        password="user1",
        host="localhost",
        port=5432
    )
    cur = conn.cursor()

    # Crear tabla si no existe
    cur.execute("""
    CREATE TABLE IF NOT EXISTS clasificacion_laliga (
        temporada TEXT,
        jornada INTEGER,
        equipo TEXT,
        posicion INTEGER,
        pj INTEGER,
        pg INTEGER,
        pe INTEGER,
        pp INTEGER,
        gf INTEGER,
        gc INTEGER,
        dg INTEGER,
        pts INTEGER,
        racha5partidos TEXT
    );
    """)
    conn.commit()

    # Insertar datos
    for _, row in df.iterrows():
        cur.execute("""
        INSERT INTO clasificacion_laliga (
            temporada, jornada, equipo, posicion,
            pj, pg, pe, pp, gf, gc, dg, pts, racha5partidos
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, tuple(row))
    conn.commit()

    # Mostrar 5 filas
    cur.execute("SELECT * FROM clasificacion_laliga LIMIT 5;")
    for fila in cur.fetchall():
        print(fila)

    cur.close()
    conn.close()

if __name__ == "__main__":
    crear_y_poblar_bd_clasificicion(CSV_PATH)
