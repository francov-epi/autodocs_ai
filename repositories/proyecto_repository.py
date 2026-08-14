from core.db import get_conn


class ProyectoRepository:

    # ── proyectos ────────────────────────────────────────────────────
    @staticmethod
    def crear(data: dict) -> int:
        conn = get_conn()
        cur = conn.execute(
            """INSERT INTO proyectos
               (cliente, proceso, tecnologia, criticidad, presupuesto_hs,
                analista, transcripcion_original, estado)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'borrador')""",
            (data.get("cliente"), data.get("proceso"), data.get("tecnologia"),
             data.get("criticidad"), data.get("presupuesto_hs") or None,
             data.get("analista"), data.get("transcripcion_original")),
        )
        conn.commit()
        pid = cur.lastrowid
        conn.close()
        return pid

    @staticmethod
    def actualizar(proyecto_id: int, campos: dict) -> None:
        if not campos:
            return
        conn = get_conn()
        sets = ", ".join(f"{k} = ?" for k in campos.keys())
        valores = list(campos.values()) + [proyecto_id]
        conn.execute(
            f"UPDATE proyectos SET {sets}, actualizado = CURRENT_TIMESTAMP WHERE id = ?",
            valores,
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get(proyecto_id: int) -> dict | None:
        conn = get_conn()
        row = conn.execute("SELECT * FROM proyectos WHERE id = ?", (proyecto_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def listar() -> list:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM proyectos ORDER BY creado DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def dashboard_stats() -> dict:
        conn = get_conn()
        total = conn.execute("SELECT COUNT(*) c FROM proyectos").fetchone()["c"]
        completados = conn.execute(
            "SELECT COUNT(*) c FROM proyectos WHERE estado='completado'"
        ).fetchone()["c"]
        frenados = conn.execute(
            "SELECT COUNT(*) c FROM proyectos WHERE estado='frenado'"
        ).fetchone()["c"]
        horas = conn.execute(
            "SELECT COALESCE(SUM(presupuesto_hs),0) h FROM proyectos WHERE presupuesto_hs IS NOT NULL"
        ).fetchone()["h"]
        alertas_abiertas = conn.execute(
            "SELECT COUNT(*) c FROM alertas WHERE resuelta = 0"
        ).fetchone()["c"]
        recientes = conn.execute(
            "SELECT id, cliente, proceso, estado, creado FROM proyectos ORDER BY creado DESC LIMIT 6"
        ).fetchall()
        conn.close()
        return {
            "total_proyectos": total,
            "completados": completados,
            "frenados": frenados,
            "horas_estimadas": round(horas, 1),
            "alertas_abiertas": alertas_abiertas,
            "recientes": [dict(r) for r in recientes],
        }

    # ── documentos ───────────────────────────────────────────────────
    @staticmethod
    def guardar_documento(proyecto_id: int, tipo: str, contenido: str) -> None:
        conn = get_conn()
        ultima = conn.execute(
            "SELECT COALESCE(MAX(version),0) v FROM documentos WHERE proyecto_id=? AND tipo=?",
            (proyecto_id, tipo),
        ).fetchone()["v"]
        conn.execute(
            "INSERT INTO documentos (proyecto_id, tipo, contenido, version) VALUES (?, ?, ?, ?)",
            (proyecto_id, tipo, contenido, ultima + 1),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_documentos(proyecto_id: int) -> dict:
        """Devuelve el último documento de cada tipo para el proyecto."""
        conn = get_conn()
        rows = conn.execute(
            """SELECT d.* FROM documentos d
               INNER JOIN (
                 SELECT tipo, MAX(version) mv FROM documentos
                 WHERE proyecto_id = ? GROUP BY tipo
               ) top ON d.tipo = top.tipo AND d.version = top.mv
               WHERE d.proyecto_id = ?""",
            (proyecto_id, proyecto_id),
        ).fetchall()
        conn.close()
        return {r["tipo"]: dict(r) for r in rows}

    # ── logs agénticos ───────────────────────────────────────────────
    @staticmethod
    def log(proyecto_id: int, gem: str, mensaje: str, nivel: str = "info") -> None:
        conn = get_conn()
        conn.execute(
            "INSERT INTO logs_agenticos (proyecto_id, gem, mensaje, nivel) VALUES (?, ?, ?, ?)",
            (proyecto_id, gem, mensaje, nivel),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_logs(proyecto_id: int) -> list:
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM logs_agenticos WHERE proyecto_id = ? ORDER BY id ASC", (proyecto_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── alertas ──────────────────────────────────────────────────────
    @staticmethod
    def agregar_alerta(proyecto_id: int, tipo: str, mensaje: str) -> None:
        conn = get_conn()
        conn.execute(
            "INSERT INTO alertas (proyecto_id, tipo, mensaje) VALUES (?, ?, ?)",
            (proyecto_id, tipo, mensaje),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_alertas(proyecto_id: int) -> list:
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM alertas WHERE proyecto_id = ? ORDER BY id ASC", (proyecto_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
