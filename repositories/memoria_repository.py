from core.db import get_conn


class MemoriaRepository:
    """Memoria de Largo Plazo / Conocimiento Organizacional (punto 6).

    Implementación de referencia sobre SQLite con búsqueda por coincidencia
    de tags. En producción, según el stack propuesto en el Trabajo de Medio
    Ciclo, esta tabla migra a PostgreSQL + pgvector y la búsqueda pasa a ser
    por similitud semántica de embeddings; la interfaz pública de este
    repositorio (agregar / buscar_relevante / listar) no necesitaría cambiar.
    """

    @staticmethod
    def agregar(tipo: str, tags: list, contenido: str, proyecto_origen_id: int = None) -> None:
        conn = get_conn()
        conn.execute(
            """INSERT INTO memoria_organizacional (tipo, tags, contenido, proyecto_origen_id)
               VALUES (?, ?, ?, ?)""",
            (tipo, ",".join(tags), contenido, proyecto_origen_id),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def buscar_relevante(texto: str, limite: int = 5) -> list:
        """Búsqueda por palabras clave (placeholder de búsqueda semántica)."""
        palabras = {p.strip(".,;:()").lower() for p in texto.split() if len(p) > 3}
        conn = get_conn()
        rows = conn.execute("SELECT * FROM memoria_organizacional").fetchall()
        conn.close()

        coincidencias = []
        for r in rows:
            tags = {t.strip().lower() for t in (r["tags"] or "").split(",") if t.strip()}
            score = len(palabras & tags)
            if score > 0:
                coincidencias.append((score, dict(r)))
        coincidencias.sort(key=lambda x: x[0], reverse=True)
        return [c[1] for c in coincidencias[:limite]]

    @staticmethod
    def listar(limite: int = 100) -> list:
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM memoria_organizacional ORDER BY creado DESC LIMIT ?", (limite,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
