import io
import zipfile

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file

from core.config_manager import ConfigManager
from ai.providers.gemini_provider import AVAILABLE_MODELS as GEMINI_MODELS
from repositories.proyecto_repository import ProyectoRepository
from services.gems_service import GemsService
from services.memoria_service import MemoriaService
from services.export_service import ExportService
from pipeline.relevamiento_pipeline import RelevamientoPipeline

_TIPOS_DOC = ["PDD", "SDD", "QA", "ESTIMACION"]
_GEM_POR_TIPO = {"PDD": "pdd", "SDD": "sdd", "QA": "qa", "ESTIMACION": "estimacion"}


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "autodocs-ai-secret-2026"

    # ── dashboard ────────────────────────────────────────────────────
    @app.route("/")
    def dashboard():
        stats = ProyectoRepository.dashboard_stats()
        key_status = ConfigManager.key_status()
        return render_template("index.html", stats=stats, key_status=key_status)

    # ── historial de proyectos ───────────────────────────────────────
    @app.route("/proyectos")
    def proyectos():
        return render_template("proyectos.html", proyectos=ProyectoRepository.listar())

    # ── interfaz de entrada (Figura 3) ───────────────────────────────
    @app.route("/relevamiento/nuevo", methods=["GET", "POST"])
    def nuevo_relevamiento():
        if request.method == "POST":
            data = request.get_json(silent=True) or request.form.to_dict()
            presupuesto = data.get("presupuesto_hs") or None
            proyecto_id = ProyectoRepository.crear({
                "cliente": data.get("cliente", "").strip(),
                "proceso": data.get("proceso", "").strip(),
                "tecnologia": data.get("tecnologia"),
                "criticidad": data.get("criticidad"),
                "presupuesto_hs": float(presupuesto) if presupuesto else None,
                "analista": data.get("analista", "").strip(),
                "transcripcion_original": data.get("transcripcion", "").strip(),
            })
            if request.is_json:
                return jsonify({"ok": True, "id": proyecto_id})
            return redirect(url_for("procesamiento", proyecto_id=proyecto_id, autostart=1))
        return render_template("nuevo_relevamiento.html")

    # ── interfaz de procesamiento (Figura 4) ─────────────────────────
    @app.route("/procesamiento/<int:proyecto_id>")
    def procesamiento(proyecto_id):
        proyecto = ProyectoRepository.get(proyecto_id)
        if not proyecto:
            return redirect(url_for("proyectos"))
        return render_template(
            "procesamiento.html",
            proyecto=proyecto,
            autostart=request.args.get("autostart") == "1",
        )

    @app.route("/api/proyecto/<int:proyecto_id>/iniciar", methods=["POST"])
    def api_iniciar_proyecto(proyecto_id):
        RelevamientoPipeline.procesar(proyecto_id)
        return jsonify({"ok": True})

    @app.route("/api/proyecto/<int:proyecto_id>/estado")
    def api_estado_proyecto(proyecto_id):
        proyecto = ProyectoRepository.get(proyecto_id)
        if not proyecto:
            return jsonify({"error": "No encontrado"}), 404
        return jsonify({
            "estado": proyecto["estado"],
            "motivo_freno": proyecto["motivo_freno"],
            "logs": ProyectoRepository.get_logs(proyecto_id),
            "alertas": ProyectoRepository.get_alertas(proyecto_id),
        })

    # ── interfaz de salida (Figura 5) ────────────────────────────────
    @app.route("/resultado/<int:proyecto_id>")
    def resultado(proyecto_id):
        proyecto = ProyectoRepository.get(proyecto_id)
        if not proyecto:
            return redirect(url_for("proyectos"))
        documentos = ProyectoRepository.get_documentos(proyecto_id)
        alertas = ProyectoRepository.get_alertas(proyecto_id)
        return render_template(
            "resultado.html",
            proyecto=proyecto,
            documentos=documentos,
            tipos=_TIPOS_DOC,
            alertas=alertas,
        )

    @app.route("/api/proyecto/<int:proyecto_id>/editar", methods=["POST"])
    def api_editar_documento(proyecto_id):
        """Edición conversacional: 'Gem SDD, cambiá la arquitectura a...'"""
        data = request.get_json(silent=True) or {}
        tipo = (data.get("tipo") or "").upper()
        instruccion = (data.get("instruccion") or "").strip()
        if tipo not in _TIPOS_DOC or not instruccion:
            return jsonify({"error": "Faltan campos tipo/instruccion"}), 400

        documentos = ProyectoRepository.get_documentos(proyecto_id)
        actual = documentos.get(tipo, {}).get("contenido", "")
        gem_key = _GEM_POR_TIPO[tipo]

        nuevo_contenido = GemsService.invocar(
            gem_key, proyecto_id,
            contenido=(
                f"Versión actual del documento {tipo}:\n{actual}\n\n"
                f"Pedido de edición del analista: {instruccion}\n\n"
                "Devolvé el documento completo ya actualizado."
            ),
            etiqueta_log=f"Edición {tipo}",
        )
        ProyectoRepository.guardar_documento(proyecto_id, tipo, nuevo_contenido)
        return jsonify({"ok": True, "contenido": nuevo_contenido})

    @app.route("/api/proyecto/<int:proyecto_id>/feedback", methods=["POST"])
    def api_feedback(proyecto_id):
        """Evaluación → Aprendizaje: el analista registra una corrección
        que debe pasar a la memoria organizacional para futuros proyectos."""
        data = request.get_json(silent=True) or {}
        contenido = (data.get("contenido") or "").strip()
        tags = [t.strip() for t in (data.get("tags") or "").split(",") if t.strip()]
        if not contenido:
            return jsonify({"error": "El feedback está vacío"}), 400
        MemoriaService.registrar_aprendizaje(proyecto_id, "feedback", tags, contenido)
        ProyectoRepository.log(proyecto_id, "Memoria",
                                "Nuevo criterio registrado por el analista (aprendizaje continuo)", "ok")
        return jsonify({"ok": True})

    # ── exportación ──────────────────────────────────────────────────
    @app.route("/export/<int:proyecto_id>/<tipo>")
    def export_documento(proyecto_id, tipo):
        tipo = tipo.upper()
        proyecto = ProyectoRepository.get(proyecto_id)
        documentos = ProyectoRepository.get_documentos(proyecto_id)
        if not proyecto or tipo not in documentos:
            return jsonify({"error": "No encontrado"}), 404
        contenido = documentos[tipo]["contenido"]

        nombre_base = f"{tipo}_{proyecto['cliente']}_{proyecto['proceso']}".replace(" ", "_")
        if tipo == "PDD":
            buf = ExportService.pdd_a_docx(proyecto, contenido)
            return send_file(buf, as_attachment=True, download_name=f"{nombre_base}.docx")
        if tipo == "SDD":
            buf = ExportService.sdd_a_docx(proyecto, contenido)
            return send_file(buf, as_attachment=True, download_name=f"{nombre_base}.docx")
        if tipo == "QA":
            buf = ExportService.qa_a_xlsx(proyecto, contenido)
            return send_file(buf, as_attachment=True, download_name=f"{nombre_base}.xlsx")
        if tipo == "ESTIMACION":
            buf = ExportService.estimacion_a_xlsx(proyecto, contenido)
            return send_file(buf, as_attachment=True, download_name=f"{nombre_base}.xlsx")
        return jsonify({"error": "Tipo desconocido"}), 400

    @app.route("/export/<int:proyecto_id>/paquete")
    def export_paquete(proyecto_id):
        proyecto = ProyectoRepository.get(proyecto_id)
        documentos = ProyectoRepository.get_documentos(proyecto_id)
        if not proyecto:
            return jsonify({"error": "No encontrado"}), 404

        mem_buf = io.BytesIO()
        with zipfile.ZipFile(mem_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if "PDD" in documentos:
                zf.writestr("PDD.docx", ExportService.pdd_a_docx(proyecto, documentos["PDD"]["contenido"]).read())
            if "SDD" in documentos:
                zf.writestr("SDD.docx", ExportService.sdd_a_docx(proyecto, documentos["SDD"]["contenido"]).read())
            if "QA" in documentos:
                zf.writestr("Casos_de_Prueba.xlsx", ExportService.qa_a_xlsx(proyecto, documentos["QA"]["contenido"]).read())
            if "ESTIMACION" in documentos:
                zf.writestr("Estimacion.xlsx", ExportService.estimacion_a_xlsx(proyecto, documentos["ESTIMACION"]["contenido"]).read())
        mem_buf.seek(0)
        nombre = f"AutoDocsAI_{proyecto['cliente']}_{proyecto['proceso']}".replace(" ", "_")
        return send_file(mem_buf, as_attachment=True, download_name=f"{nombre}.zip")

    # ── memoria organizacional ───────────────────────────────────────
    @app.route("/memoria")
    def memoria():
        return render_template("memoria.html", entradas=MemoriaService.listar())

    # ── configuración ────────────────────────────────────────────────
    @app.route("/configuracion", methods=["GET", "POST"])
    def configuracion():
        if request.method == "POST":
            form = request.form
            nuevo_cfg = {
                "providers": {
                    "gemini": {
                        "env_key_name": form.get("gemini_env_name"),
                        "model": form.get("gemini_model"),
                    },
                },
                "gems": {},
                "reglas": {
                    "duracion_min_minutos": int(form.get("duracion_min_minutos") or 3),
                },
            }
            for gem_key in ["ingesta", "pdd", "sdd", "qa", "estimacion", "supervisor"]:
                nuevo_cfg["gems"][gem_key] = {
                    "model": form.get(f"{gem_key}_model"),
                    "system_instruction": form.get(f"{gem_key}_instruction", ""),
                }
            ConfigManager.save(nuevo_cfg)
            return redirect(url_for("configuracion"))

        cfg = ConfigManager.load()
        return render_template(
            "settings.html",
            cfg=cfg,
            key_status=ConfigManager.key_status(),
            gemini_models=GEMINI_MODELS,
        )

    @app.route("/api/test-gemini")
    def api_test_gemini():
        return jsonify(GemsService.probar_conexion())

    @app.route("/api/gemini/modelos")
    def api_gemini_modelos():
        return jsonify(GemsService.listar_modelos_disponibles())

    return app
