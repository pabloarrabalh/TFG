import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import norm
import os

# Configuración
CSV_PATH = "csv/csvGenerados/players_with_features.csv"
POSICIONES = ["PT", "DF", "MC", "DT"]
COLUMNA_PUNTOS = "puntos_fantasy"
COLUMNA_POSICION = "posicion"

def calcula_rangos_mae_fino(mae_serie):
    """
    Calcula rangos utilizando percentiles. 
    Esto es mucho más robusto para distribuciones no normales.
    """
    # Eliminamos NaNs para evitar errores en el cálculo de cuantiles
    mae_clean = mae_serie.dropna()
    
    if mae_clean.empty:
        return {"excelente": 0, "bueno": 0, "pobre": 0}

    return {
        # El 25% de los jugadores con menos error
        "excelente": mae_clean.quantile(0.25), 
        # El error mediano (punto medio real)
        "bueno": mae_clean.median(),           
        # El 75% (solo el 25% restante tiene errores mayores)
        "pobre": mae_clean.quantile(0.75)      
    }

def clasifica_mae(mae, rangos):
    if mae <= rangos["excelente"]:
        return "Excelente"
    elif mae <= rangos["bueno"]:
        return "Bueno"
    elif mae <= rangos["pobre"]:
        return "Pobre"
    else:
        return "Muy pobre"

def main():
    # 1. Carga y Limpieza de datos
    if not os.path.exists(CSV_PATH):
        print(f"Error: No se encuentra el archivo en {CSV_PATH}")
        return

    df = pd.read_csv(CSV_PATH)
    
    # Estandarizar posiciones
    df[COLUMNA_POSICION] = df[COLUMNA_POSICION].astype(str).str.strip().str.upper()
    df = df[df[COLUMNA_POSICION].isin(POSICIONES)]
    
    # Asegurar puntos numéricos y filtrar outliers
    df[COLUMNA_PUNTOS] = pd.to_numeric(df[COLUMNA_PUNTOS], errors='coerce')
    df = df.dropna(subset=[COLUMNA_PUNTOS])
    df = df[df[COLUMNA_PUNTOS] <= 40]

    resumen_rangos = []
    colores = {"PT": "blue", "DF": "green", "MC": "orange", "DT": "purple"}
    
    plt.figure(figsize=(12, 7))
    x_global = np.linspace(df[COLUMNA_PUNTOS].min(), df[COLUMNA_PUNTOS].max(), 200)
    media_global = df[COLUMNA_PUNTOS].mean()
    std_global = df[COLUMNA_PUNTOS].std()

    # 2. Procesamiento por posición
    for pos in POSICIONES:
        df_pos = df[df[COLUMNA_POSICION] == pos]
        datos_puntos = df_pos[COLUMNA_PUNTOS]
        
        if len(datos_puntos) < 10:
            print(f"Saltando {pos}: Datos insuficientes.")
            continue

        # Media de la posición para usar como baseline de predicción simple
        media_pos = datos_puntos.mean()
        
        # Calculamos el MAE de cada jugador respecto a la media de su posición
        # (Esto mide qué tan difícil es predecir a ese jugador usando la media posicional)
        mae_jugadores = df_pos.groupby("player")[COLUMNA_PUNTOS].apply(
            lambda x: np.mean(np.abs(x - media_pos))
        )
        
        # Calculamos los nuevos rangos finos
        rangos = calcula_rangos_mae_fino(mae_jugadores)
        
        # Clasificamos
        clasificaciones = mae_jugadores.apply(lambda x: clasifica_mae(x, rangos))
        resumen_jugadores = mae_jugadores.to_frame("MAE").assign(Rango=clasificaciones)
        
        # MAE Relativo: ¿Qué % representa el error sobre la media de puntos?
        mae_medio_pos = mae_jugadores.mean()
        mae_relativo_pct = (mae_medio_pos / media_pos) * 100 if media_pos != 0 else 0

        # Guardar resultados para la tabla final
        resumen_rangos.append({
            "Posición": pos,
            "Media Puntos": media_pos,
            "MAE Medio": mae_medio_pos,
            "Error %": f"{mae_relativo_pct:.1f}%",
            "Excelente (P25)": rangos["excelente"],
            "Bueno (Mediana)": rangos["bueno"],
            "Pobre (P75)": rangos["pobre"]
        })

        # Visualización
        sns.kdeplot(datos_puntos, label=f"{pos}", color=colores[pos], linewidth=2.5)

        print(f"\n>>> Análisis Posición: {pos}")
        print(f"Media puntos: {media_pos:.2f} | MAE Promedio: {mae_medio_pos:.2f}")


    # 3. Finalizar Gráfica
    plt.plot(x_global, norm.pdf(x_global, media_global, std_global), 
             linestyle="--", color="black", label="Referencia Normal", alpha=0.6)
    
    plt.title("Distribución de Puntos por Posición (Análisis de Volatilidad)", fontsize=14)
    plt.xlabel("Puntos Fantasy")
    plt.ylabel("Densidad de probabilidad")
    plt.grid(axis='y', alpha=0.3)
    plt.legend()
    plt.tight_layout()

    # Guardar imagen
    script_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else "."
    output_path = os.path.join(script_dir, "comparativa_distribuciones_fino.png")
    plt.savefig(output_path)
    plt.close()

    # 4. Mostrar Tabla de Resumen
    tabla = pd.DataFrame(resumen_rangos)
    print("\n" + "="*85)
    print("RESUMEN DE RANGOS DE PRECISIÓN (MÉTODO PERCENTILES)")
    print("="*85)
    print(tabla.to_string(index=False, justify='center'))
    print("="*85)
    print(f"Gráfica guardada en: {output_path}")

if __name__ == "__main__":
    main()