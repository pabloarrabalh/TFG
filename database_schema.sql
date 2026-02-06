-- ============================================================================
-- ESQUEMA DE BASE DE DATOS - ANÁLISIS DE FÚTBOL
-- ============================================================================
-- Este script crea la estructura de BD para almacenar:
-- - Temporadas (Competiciones) y jornadas
-- - Equipos y jugadores
-- - Partidos con resultados
-- - Estadísticas de jugadores por partido
-- - Rendimiento histórico de jugadores
-- - Clasificaciones por jornada

-- ============================================================================
-- TIPO ENUM: ESTADO DEL PARTIDO
-- ============================================================================
CREATE TYPE estado_partido AS ENUM ('JUGADO', 'PENDIENTE', 'APLAZADO');

-- ============================================================================
-- TABLA: TEMPORADAS (Competiciones)
-- ============================================================================
CREATE TABLE temporadas (
    id_temporada SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL  -- Ej: "La Liga 2023-24", "La Liga 2024-25"
);

-- ============================================================================
-- TABLA: EQUIPOS
-- ============================================================================
CREATE TABLE equipos (
    id_equipo SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    estadio VARCHAR(150) NOT NULL
);

-- ============================================================================
-- TABLA: EQUIPOS EN TEMPORADAS
-- ============================================================================
-- Relaciona equipos con temporadas (permite ascensos/descensos)
CREATE TABLE equipos_temporada (
    id_equipo_temporada SERIAL PRIMARY KEY,
    id_equipo INT NOT NULL,
    id_temporada INT NOT NULL,
    FOREIGN KEY (id_equipo) REFERENCES equipos(id_equipo) ON DELETE CASCADE,
    FOREIGN KEY (id_temporada) REFERENCES temporadas(id_temporada) ON DELETE CASCADE,
    CONSTRAINT unique_equipo_temporada UNIQUE(id_equipo, id_temporada)
);

-- ============================================================================
-- TABLA: JUGADORES
-- ============================================================================
CREATE TABLE jugadores (
    id_jugador SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    apellido VARCHAR(150) NOT NULL,
    posicion VARCHAR(30) NOT NULL,  -- Portero, Defensa, Centrocampista, Delantero
    nacionalidad VARCHAR(100) NOT NULL
);

-- ============================================================================
-- TABLA: HISTORIAL DE EQUIPOS DE JUGADORES
-- ============================================================================
-- Registra cada cambio de equipo de un jugador (entre temporadas o durante la misma)
CREATE TABLE historial_equipos_jugador (
    id_historial SERIAL PRIMARY KEY,
    id_jugador INT NOT NULL,
    id_equipo INT NOT NULL,
    id_temporada INT NOT NULL,
    dorsal INT NOT NULL,
    edad INT NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE,  -- NULL si sigue en el equipo
    FOREIGN KEY (id_jugador) REFERENCES jugadores(id_jugador) ON DELETE CASCADE,
    FOREIGN KEY (id_equipo) REFERENCES equipos(id_equipo) ON DELETE CASCADE,
    FOREIGN KEY (id_temporada) REFERENCES temporadas(id_temporada) ON DELETE CASCADE
);

-- ============================================================================
-- TABLA: JORNADAS
-- ============================================================================
CREATE TABLE jornadas (
    id_jornada SERIAL PRIMARY KEY,
    id_temporada INT NOT NULL,
    numero_jornada INT NOT NULL,
    fecha_inicio DATE,
    fecha_fin DATE,
    FOREIGN KEY (id_temporada) REFERENCES temporadas(id_temporada) ON DELETE CASCADE,
    CONSTRAINT unique_jornada_temporada UNIQUE(id_temporada, numero_jornada)
);

-- ============================================================================
-- TABLA: PARTIDOS
-- ============================================================================
CREATE TABLE partidos (
    id_partido SERIAL PRIMARY KEY,
    id_jornada INT NOT NULL,
    id_equipo_local INT NOT NULL,
    id_equipo_visitante INT NOT NULL,
    fecha_partido TIMESTAMP,
    goles_local INT,
    goles_visitante INT,
    estado estado_partido DEFAULT 'PENDIENTE',
    FOREIGN KEY (id_jornada) REFERENCES jornadas(id_jornada) ON DELETE CASCADE,
    FOREIGN KEY (id_equipo_local) REFERENCES equipos(id_equipo),
    FOREIGN KEY (id_equipo_visitante) REFERENCES equipos(id_equipo),
    CONSTRAINT diferente_equipo CHECK (id_equipo_local != id_equipo_visitante)
);

-- ============================================================================
-- TABLA: CLASIFICACIÓN POR JORNADA
-- ============================================================================
-- Almacena el estado de la clasificación después de cada jornada
CREATE TABLE clasificacion_jornada (
    id_clasificacion SERIAL PRIMARY KEY,
    id_temporada INT NOT NULL,
    id_jornada INT NOT NULL,
    id_equipo INT NOT NULL,
    posicion INT NOT NULL,
    puntos INT DEFAULT 0,
    goles_favor INT DEFAULT 0,
    goles_contra INT DEFAULT 0,
    diferencia_goles INT DEFAULT 0,
    partidos_ganados INT DEFAULT 0,
    partidos_empatados INT DEFAULT 0,
    partidos_perdidos INT DEFAULT 0,
    racha_reciente VARCHAR(50),  -- Ej: "VGVEG" (V=victoria, G=derrota, E=empate)
    FOREIGN KEY (id_temporada) REFERENCES temporadas(id_temporada) ON DELETE CASCADE,
    FOREIGN KEY (id_jornada) REFERENCES jornadas(id_jornada) ON DELETE CASCADE,
    FOREIGN KEY (id_equipo) REFERENCES equipos(id_equipo) ON DELETE CASCADE,
    CONSTRAINT unique_clasificacion UNIQUE(id_temporada, id_jornada, id_equipo)
);

-- ============================================================================
-- TABLA: ESTADÍSTICAS DE PARTIDO POR JUGADOR
-- ============================================================================
-- Almacena las estadísticas de cada jugador en cada partido
CREATE TABLE estadisticas_partido_jugador (
    id_estadistica SERIAL PRIMARY KEY,
    id_partido INT NOT NULL,
    id_jugador INT NOT NULL,
    minutos_jugados INT DEFAULT 0,
    goles INT DEFAULT 0,
    asistencias INT DEFAULT 0,
    disparos INT DEFAULT 0,
    disparos_a_puerta INT DEFAULT 0,
    pases_completados INT DEFAULT 0,
    pases_totales INT DEFAULT 0,
    regates INT DEFAULT 0,
    despejes INT DEFAULT 0,
    faltas_cometidas INT DEFAULT 0,
    tarjetas_amarillas INT DEFAULT 0,
    tarjetas_rojas INT DEFAULT 0,
    recuperaciones INT DEFAULT 0,
    intercepciones INT DEFAULT 0,
    entradas INT DEFAULT 0,
    duelos_ganados INT DEFAULT 0,
    duelos_totales INT DEFAULT 0,
    calificacion_decimal DECIMAL(3, 1),
    en_alineacion BOOLEAN DEFAULT TRUE,
    fue_suplente BOOLEAN DEFAULT FALSE,
    minuto_salida INT,
    minuto_entrada INT,
    gol_en_propia_puerta BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (id_partido) REFERENCES partidos(id_partido) ON DELETE CASCADE,
    FOREIGN KEY (id_jugador) REFERENCES jugadores(id_jugador) ON DELETE CASCADE,
    CONSTRAINT unique_jugador_partido UNIQUE(id_partido, id_jugador)
);

-- ============================================================================
-- TABLA: RENDIMIENTO HISTÓRICO DE JUGADORES
-- ============================================================================
CREATE TABLE rendimiento_historico_jugador (
    id_rendimiento SERIAL PRIMARY KEY,
    id_jugador INT NOT NULL,
    id_temporada INT NOT NULL,
    id_equipo INT NOT NULL,
    partidos_jugados INT DEFAULT 0,
    partidos_como_titular INT DEFAULT 0,
    minutos_totales INT DEFAULT 0,
    goles_temporada INT DEFAULT 0,
    asistencias_temporada INT DEFAULT 0,
    tarjetas_amarillas_total INT DEFAULT 0,
    tarjetas_rojas_total INT DEFAULT 0,
    promedio_calificacion DECIMAL(3, 1),
    pases_completados_total INT DEFAULT 0,
    goles_en_propia_puerta_total INT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_jugador) REFERENCES jugadores(id_jugador) ON DELETE CASCADE,
    FOREIGN KEY (id_temporada) REFERENCES temporadas(id_temporada) ON DELETE CASCADE,
    FOREIGN KEY (id_equipo) REFERENCES equipos(id_equipo),
    CONSTRAINT unique_jugador_temporada UNIQUE(id_jugador, id_temporada)
);

-- ============================================================================
-- ÍNDICES PARA OPTIMIZACIÓN
-- ============================================================================
CREATE INDEX idx_jugadores_equipo ON jugadores(id_equipo);
CREATE INDEX idx_jugadores_temporada ON jugadores(id_temporada);
CREATE INDEX idx_equipos_temporada ON equipos_temporada(id_equipo);
CREATE INDEX idx_temporadas_equipos ON equipos_temporada(id_temporada);
CREATE INDEX idx_partidos_jornada ON partidos(id_jornada);
CREATE INDEX idx_partidos_equipo_local ON partidos(id_equipo_local);
CREATE INDEX idx_partidos_equipo_visitante ON partidos(id_equipo_visitante);
CREATE INDEX idx_partidos_fecha ON partidos(fecha_partido);
CREATE INDEX idx_estadisticas_partido ON estadisticas_partido_jugador(id_partido);
CREATE INDEX idx_estadisticas_jugador ON estadisticas_partido_jugador(id_jugador);
CREATE INDEX idx_rendimiento_jugador ON rendimiento_historico_jugador(id_jugador);
CREATE INDEX idx_rendimiento_temporada ON rendimiento_historico_jugador(id_temporada);
CREATE INDEX idx_historial_jugador ON historial_equipos_jugador(id_jugador);
CREATE INDEX idx_historial_equipo ON historial_equipos_jugador(id_equipo);
CREATE INDEX idx_historial_temporada ON historial_equipos_jugador(id_temporada);
CREATE INDEX idx_historial_fechas ON historial_equipos_jugador(fecha_inicio, fecha_fin);

-- ============================================================================
-- EJEMPLOS DE INSERCIÓN DE DATOS
-- ============================================================================

-- Insertar temporadas
INSERT INTO temporadas (nombre) VALUES
('La Liga 2023-24'),
('La Liga 2024-25'),
('La Liga 2025-26');

-- Insertar equipos
INSERT INTO equipos (nombre, estadio) VALUES
('Real Madrid', 'Santiago Bernabéu'),
('FC Barcelona', 'Camp Nou'),
('Atlético Madrid', 'Wanda Metropolitano'),
('Real Sociedad', 'Anoeta'),
('Athletic Club', 'San Mamés'),
('Sevilla FC', 'Ramón Sánchez-Pizjuán'),
('Valencia CF', 'Mestalla'),
('Real Betis', 'Benito Villamarín'),
('Villarreal CF', 'Estadio de la Cerámica'),
('Getafe CF', 'Coliseum Alfonso Pérez');

-- Insertar jugadores (sin equipo ni temporada específica)
INSERT INTO jugadores (nombre, apellido, posicion, nacionalidad) VALUES
('Kylian', 'Mbappé', 'Delantero', 'Francia'),
('Vinícius', 'Júnior', 'Delantero', 'Brasil'),
('Robert', 'Lewandowski', 'Delantero', 'Polonia'),
('Pedri', 'González', 'Centrocampista', 'España'),
('Antoine', 'Griezmann', 'Delantero', 'Francia'),
('Jan', 'Oblak', 'Portero', 'Eslovenia');

-- Historial de equipos de jugadores (permite cambios de equipo dentro o entre temporadas)
INSERT INTO historial_equipos_jugador (id_jugador, id_equipo, id_temporada, dorsal, edad, fecha_inicio, fecha_fin) VALUES
-- Mbappé: Real Madrid 2024-25 y 2025-26
(1, 1, 2, 9, 25, '2024-08-01', NULL),
(1, 1, 3, 9, 26, '2025-08-01', NULL),
-- Vinícius Jr: Real Madrid 2024-25 y 2025-26
(2, 1, 2, 20, 23, '2024-08-01', NULL),
(2, 1, 3, 20, 24, '2025-08-01', NULL),
-- Lewandowski: Barcelona 2024-25 y cambio a Real Sociedad en 2025-26 (cambio entre temporadas)
(3, 2, 2, 9, 35, '2024-08-01', '2025-06-30'),
(3, 4, 3, 12, 36, '2025-08-01', NULL),
-- Pedri: Barcelona 2024-25 y 2025-26
(4, 2, 2, 8, 21, '2024-08-01', NULL),
(4, 2, 3, 8, 22, '2025-08-01', NULL),
-- Griezmann: Atlético 2024-25, cambio a Valencia en enero, regresa a Atlético 2025-26 (cambio dentro de temporada)
(5, 3, 2, 8, 32, '2024-08-01', '2025-01-31'),
(5, 7, 2, 15, 32, '2025-02-01', '2025-06-30'),
(5, 3, 3, 8, 33, '2025-08-01', NULL),
-- Oblak: Atlético 2024-25 y 2025-26
(6, 3, 2, 1, 30, '2024-08-01', NULL),
(6, 3, 3, 1, 31, '2025-08-01', NULL);

-- Insertar jornadas
INSERT INTO jornadas (id_temporada, numero_jornada, fecha_inicio, fecha_fin) VALUES
(1, 1, '2023-08-15', '2023-08-22'),
(1, 2, '2023-08-22', '2023-08-29'),
(1, 3, '2023-08-29', '2023-09-05'),
(2, 1, '2024-08-15', '2024-08-22'),
(2, 2, '2024-08-22', '2024-08-29'),
(3, 1, '2025-08-15', '2025-08-22');

-- Insertar partidos
INSERT INTO partidos (id_jornada, id_equipo_local, id_equipo_visitante, fecha_partido, goles_local, goles_visitante, estado) VALUES
(1, 1, 2, '2023-08-16 20:00:00', 3, 1, 'JUGADO'),
(1, 3, 4, '2023-08-17 19:30:00', 2, 2, 'JUGADO'),
(2, 5, 1, '2023-08-23 20:00:00', 1, 2, 'JUGADO'),
(2, 2, 3, '2023-08-24 19:00:00', NULL, NULL, 'PENDIENTE'),
(3, 4, 5, '2023-09-01 19:00:00', NULL, NULL, 'PENDIENTE'),
(3, 1, 3, '2023-09-02 20:00:00', NULL, NULL, 'PENDIENTE');

-- ============================================================================
-- VISTAS ÚTILES
-- ============================================================================

-- Vista: Resumen de partidos con nombres de equipos
CREATE VIEW v_partidos_resumen AS
SELECT 
    p.id_partido,
    j.numero_jornada,
    t.nombre AS temporada,
    p.fecha_partido,
    el.nombre AS equipo_local,
    ev.nombre AS equipo_visitante,
    p.goles_local,
    p.goles_visitante,
    p.estado
FROM partidos p
JOIN jornadas j ON p.id_jornada = j.id_jornada
JOIN temporadas t ON j.id_temporada = t.id_temporada
JOIN equipos el ON p.id_equipo_local = el.id_equipo
JOIN equipos ev ON p.id_equipo_visitante = ev.id_equipo
ORDER BY p.fecha_partido DESC NULLS LAST;

-- Vista: Clasificación completa por jornada
CREATE VIEW v_clasificacion_por_jornada AS
SELECT 
    t.nombre AS temporada,
    j.numero_jornada,
    cj.posicion,
    e.nombre AS equipo,
    e.estadio,
    cj.puntos,
    cj.partidos_ganados,
    cj.partidos_empatados,
    cj.partidos_perdidos,
    cj.goles_favor,
    cj.goles_contra,
    cj.diferencia_goles,
    cj.racha_reciente
FROM clasificacion_jornada cj
JOIN temporadas t ON cj.id_temporada = t.id_temporada
JOIN jornadas j ON cj.id_jornada = j.id_jornada
JOIN equipos e ON cj.id_equipo = e.id_equipo
ORDER BY t.nombre DESC, j.numero_jornada DESC, cj.posicion ASC;

-- Vista: Partidos de un equipo específico
CREATE VIEW v_partidos_por_equipo AS
SELECT 
    e.nombre AS equipo,
    t.nombre AS temporada,
    j.numero_jornada,
    p.fecha_partido,
    CASE 
        WHEN p.id_equipo_local = e.id_equipo THEN 'LOCAL'
        ELSE 'VISITANTE'
    END AS condicion,
    CASE 
        WHEN p.id_equipo_local = e.id_equipo THEN ev.nombre
        ELSE el.nombre
    END AS rival,
    CASE 
        WHEN p.id_equipo_local = e.id_equipo THEN p.goles_local
        ELSE p.goles_visitante
    END AS goles_a_favor,
    CASE 
        WHEN p.id_equipo_local = e.id_equipo THEN p.goles_visitante
        ELSE p.goles_local
    END AS goles_en_contra,
    p.estado
FROM partidos p
JOIN jornadas j ON p.id_jornada = j.id_jornada
JOIN temporadas t ON j.id_temporada = t.id_temporada
JOIN equipos e ON (p.id_equipo_local = e.id_equipo OR p.id_equipo_visitante = e.id_equipo)
JOIN equipos el ON p.id_equipo_local = el.id_equipo
JOIN equipos ev ON p.id_equipo_visitante = ev.id_equipo
ORDER BY p.fecha_partido DESC NULLS LAST;

-- Vista: Jugadores de un equipo en una temporada específica
CREATE VIEW v_jugadores_por_equipo_temporada AS
SELECT 
    t.nombre AS temporada,
    e.nombre AS equipo,
    j.nombre,
    j.apellido,
    hej.dorsal,
    j.posicion,
    hej.edad,
    j.nacionalidad,
    hej.fecha_inicio,
    hej.fecha_fin
FROM historial_equipos_jugador hej
JOIN jugadores j ON hej.id_jugador = j.id_jugador
JOIN equipos e ON hej.id_equipo = e.id_equipo
JOIN temporadas t ON hej.id_temporada = t.id_temporada
ORDER BY t.nombre DESC, e.nombre, hej.fecha_inicio DESC;

-- Vista: Historial completo de un jugador (todos sus equipos)
CREATE VIEW v_historial_jugador AS
SELECT 
    j.nombre,
    j.apellido,
    j.nacionalidad,
    j.posicion,
    e.nombre AS equipo,
    t.nombre AS temporada,
    hej.dorsal,
    hej.edad,
    hej.fecha_inicio,
    hej.fecha_fin,
    CASE WHEN hej.fecha_fin IS NULL THEN 'Activo' ELSE 'Inactivo' END AS estado
FROM historial_equipos_jugador hej
JOIN jugadores j ON hej.id_jugador = j.id_jugador
JOIN equipos e ON hej.id_equipo = e.id_equipo
JOIN temporadas t ON hej.id_temporada = t.id_temporada
ORDER BY j.nombre, j.apellido, hej.fecha_inicio DESC;

-- Vista: Estadísticas de jugadores en partidos
CREATE VIEW v_estadisticas_detalladas AS
SELECT 
    j.nombre,
    j.apellido,
    e.nombre AS equipo,
    t.nombre AS temporada,
    jor.numero_jornada,
    p.fecha_partido,
    epj.minutos_jugados,
    epj.goles,
    epj.asistencias,
    epj.calificacion_decimal,
    epj.tarjetas_amarillas,
    epj.tarjetas_rojas
FROM estadisticas_partido_jugador epj
JOIN jugadores j ON epj.id_jugador = j.id_jugador
JOIN equipos e ON j.id_equipo = e.id_equipo
JOIN partidos p ON epj.id_partido = p.id_partido
JOIN jornadas jor ON p.id_jornada = jor.id_jornada
JOIN temporadas t ON jor.id_temporada = t.id_temporada
ORDER BY p.fecha_partido DESC;

-- Vista: Rendimiento de jugadores por temporada
CREATE VIEW v_rendimiento_por_temporada AS
SELECT 
    j.nombre,
    j.apellido,
    e.nombre AS equipo,
    t.nombre AS temporada,
    rhj.partidos_jugados,
    rhj.partidos_como_titular,
    rhj.minutos_totales,
    rhj.goles_temporada,
    rhj.asistencias_temporada,
    rhj.promedio_calificacion,
    rhj.tarjetas_amarillas_total,
    rhj.tarjetas_rojas_total
FROM rendimiento_historico_jugador rhj
JOIN jugadores j ON rhj.id_jugador = j.id_jugador
JOIN equipos e ON rhj.id_equipo = e.id_equipo
JOIN temporadas t ON rhj.id_temporada = t.id_temporada
ORDER BY t.nombre DESC, rhj.goles_temporada DESC;

-- ============================================================================
-- CONSULTAS ÚTILES DE EJEMPLO
-- ============================================================================

-- Obtener todos los partidos de una temporada ordenados por jornada
-- SELECT * FROM v_partidos_resumen WHERE temporada = 'La Liga 2023-24' ORDER BY numero_jornada;

-- Obtener la clasificación de una temporada en una jornada específica
-- SELECT * FROM v_clasificacion_por_jornada 
-- WHERE temporada = 'La Liga 2023-24' AND numero_jornada = 10;

-- Obtener todos los partidos de un equipo en una temporada
-- SELECT * FROM v_partidos_por_equipo 
-- WHERE equipo = 'Real Madrid' AND temporada = 'La Liga 2023-24';

-- Obtener jugadores de un equipo
-- SELECT * FROM v_jugadores_por_equipo WHERE equipo = 'Real Madrid';

-- Obtener los máximos goleadores de una temporada
-- SELECT nombre, apellido, equipo, goles_temporada FROM v_rendimiento_por_temporada 
-- WHERE temporada = 'La Liga 2023-24' ORDER BY goles_temporada DESC LIMIT 10;
