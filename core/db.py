"""
db.py — capa de persistencia (SQLite, sin dependencias externas).
Reemplaza al motor de catálogo de Wine AI OS por el dominio de AutoDocs AI:
proyectos de relevamiento, documentos generados (PDD/SDD/QA/Estimación),
log de comunicación agéntica, alertas de consistencia y memoria organizacional.

Nota de arquitectura: el Trabajo de Medio Ciclo propone PostgreSQL + pgvector
para la Memoria de Largo Plazo (búsqueda por similitud semántica de
embeddings). Esta base SQLite es la implementación de referencia/demo: la
tabla `memoria_organizacional` guarda `tags` (CSV) y se consulta por
coincidencia de palabras clave en `MemoriaService`. Migrar esa consulta a
pgvector (embeddings + cosine similarity) es un cambio acotado a
`repositories/memoria_repository.py`, sin tocar el resto del sistema.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path("data/autodocs.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS proyectos (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente                 TEXT NOT NULL,
    proceso                 TEXT NOT NULL,
    tecnologia              TEXT,       -- UiPath / Power Automate / Rocketbot / Make.com...
    criticidad              TEXT,       -- Baja / Media / Alta
    presupuesto_hs          REAL,
    analista                TEXT,
    transcripcion_original  TEXT,
    transcripcion_sanitizada TEXT,
    reemplazos_pii          INTEGER DEFAULT 0,
    flujo_estructurado      TEXT,       -- JSON: salida del Agente de Ingesta
    estado                  TEXT DEFAULT 'borrador',  -- borrador|procesando|completado|frenado|error
    motivo_freno            TEXT,       -- si estado = 'frenado' (Límite Operativo de Entrada)
    creado                  TEXT DEFAULT CURRENT_TIMESTAMP,
    actualizado             TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documentos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id INTEGER NOT NULL REFERENCES proyectos(id),
    tipo        TEXT NOT NULL,   -- PDD | SDD | QA | ESTIMACION
    contenido   TEXT,
    version     INTEGER DEFAULT 1,
    creado      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS logs_agenticos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id INTEGER NOT NULL REFERENCES proyectos(id),
    gem         TEXT NOT NULL,   -- Ingesta | Gem PDD | Gem SDD | Gem QA | Gem Estimación | Consolidador | Memoria
    mensaje     TEXT NOT NULL,
    nivel       TEXT DEFAULT 'info',  -- info | ok | warn | error
    creado      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alertas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id INTEGER NOT NULL REFERENCES proyectos(id),
    tipo        TEXT,     -- cobertura | consistencia
    mensaje     TEXT,
    resuelta    INTEGER DEFAULT 0,
    creado      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memoria_organizacional (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo              TEXT,     -- desvio_estimacion | decision_arquitectura | preferencia_estilo | feedback
    tags              TEXT,     -- csv de palabras clave para búsqueda (sustituye a la búsqueda vectorial)
    contenido         TEXT NOT NULL,
    proyecto_origen_id INTEGER REFERENCES proyectos(id),
    creado            TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Semillas de memoria organizacional: el ejemplo textual del punto 6 del
# Trabajo de Medio Ciclo ("procesos con SAP o legados requieren +20% de
# tiempo") se carga como conocimiento inicial para que la Gem Estimación
# tenga contexto desde el primer relevamiento.
_MEMORIA_SEED = [
    ("desvio_estimacion", "sap,legado,legacy,sistema legado",
     "Los procesos que involucran sistemas legados o SAP históricamente "
     "insumieron ~20% más horas que la estimación inicial. Ponderar con "
     "mayor complejidad cualquier transcripción que mencione estas tecnologías."),
]


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM memoria_organizacional")
    if cur.fetchone()["c"] == 0:
        for tipo, tags, contenido in _MEMORIA_SEED:
            cur.execute(
                "INSERT INTO memoria_organizacional (tipo, tags, contenido) VALUES (?, ?, ?)",
                (tipo, tags, contenido),
            )
    conn.commit()
    conn.close()
