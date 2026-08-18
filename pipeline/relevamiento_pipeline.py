"""
RelevamientoPipeline — orquesta el ciclo cerrado descripto en el punto 5:

  Observación (transcripción) → Análisis (Gems documentales) →
  Planificación (Consolidador) → Acción (generación de artefactos) →
  Evaluación (feedback del analista) → Aprendizaje (ajuste de criterios) →
  Nueva observación.

Este módulo es el "Agente Supervisor y Consolidador" a nivel de código: no
razona sobre el contenido (eso es de las Gems), pero sí decide el orden de
llamadas, qué le pasa a cada una, y qué se persiste en cada paso — que es
exactamente la conexión que el enunciado pide construir sin tocar la lógica
interna de cada Gem.
"""
import json

from repositories.proyecto_repository import ProyectoRepository
from services.validacion_service import ValidacionService
from services.pii_service import PiiService
from services.gems_service import GemsService
from services.memoria_service import MemoriaService
from services.consolidacion_service import ConsolidacionService


class RelevamientoPipeline:

    @staticmethod
    def procesar(proyecto_id: int) -> None:
        proyecto = ProyectoRepository.get(proyecto_id)
        if not proyecto:
            raise ValueError(f"Proyecto {proyecto_id} inexistente")

        ProyectoRepository.actualizar(proyecto_id, {"estado": "procesando"})
        ProyectoRepository.log(proyecto_id, "Pipeline", "Ciclo iniciado: Observación", "info")

        # ── 1) Observación + Límite Operativo de Entrada (punto 7) ─────
        transcripcion = proyecto["transcripcion_original"] or ""
        validacion = ValidacionService.validar_transcripcion(transcripcion)
        if not validacion["ok"]:
            motivo = " ".join(validacion["motivos"])
            ProyectoRepository.actualizar(proyecto_id, {
                "estado": "frenado",
                "motivo_freno": motivo,
            })
            ProyectoRepository.log(proyecto_id, "Pipeline",
                                    f"Frenado por Límite Operativo de Entrada: {motivo}", "warn")
            return

        # ── 2) Sanitización PII (punto 7) ───────────────────────────────
        sanitizada, reemplazos = PiiService.sanitizar(transcripcion)
        ProyectoRepository.actualizar(proyecto_id, {
            "transcripcion_sanitizada": sanitizada,
            "reemplazos_pii": reemplazos,
        })
        ProyectoRepository.log(
            proyecto_id, "Pipeline",
            f"Transcripción sanitizada ({reemplazos} reemplazos: [MOCK_DATA]/[SISTEMA_COMPARTIDO])",
            "ok",
        )

        # ── 3) Análisis — Gem de Ingesta y Estructuración ───────────────
        flujo = GemsService.invocar(
            "ingesta", proyecto_id,
            contenido=(
                f"Cliente: {proyecto['cliente']}\nProceso: {proyecto['proceso']}\n"
                f"Tecnología objetivo: {proyecto.get('tecnologia') or 'no especificada'}\n\n"
                f"Transcripción sanitizada:\n{sanitizada}"
            ),
        )
        if RelevamientoPipeline._abortar_si_error(proyecto_id, "Ingesta", flujo):
            return
        ProyectoRepository.actualizar(proyecto_id, {"flujo_estructurado": flujo})

        # ── 4) Memoria organizacional relevante (punto 6) ───────────────
        memoria_ctx = MemoriaService.contexto_relevante(
            f"{proyecto.get('tecnologia') or ''} {proyecto['proceso']} {transcripcion}"
        )
        ProyectoRepository.log(proyecto_id, "Memoria",
                                "Contexto histórico recuperado para las Gems documentales", "info")

        # ── 5) Análisis — Gems documentales (PDD, SDD, QA, Estimación) ──
        # Se ejecutan en secuencia en esta implementación de referencia;
        # en el stack propuesto (LangGraph) corren en paralelo dentro del
        # mismo nodo de "Análisis" del ciclo. Si alguna Gem falla (error de
        # API), el ciclo se corta acá: seguir mandando ese error como si
        # fuera contenido real a las Gems siguientes solo produce
        # documentos con alucinaciones sobre "no se recibió información".
        base_ctx = (
            f"Cliente: {proyecto['cliente']}\nProceso: {proyecto['proceso']}\n"
            f"Tecnología objetivo: {proyecto.get('tecnologia') or 'no especificada'}\n"
            f"Criticidad: {proyecto.get('criticidad') or 'no especificada'}\n"
            f"Presupuesto estimado (hs): {proyecto.get('presupuesto_hs') or 'no especificado'}\n\n"
            f"Flujo estructurado (Gem Ingesta):\n{flujo}\n\n{memoria_ctx}"
        )

        pdd = GemsService.invocar("pdd", proyecto_id, contenido=base_ctx)
        if RelevamientoPipeline._abortar_si_error(proyecto_id, "Gem PDD", pdd):
            return
        ProyectoRepository.guardar_documento(proyecto_id, "PDD", pdd)

        sdd = GemsService.invocar(
            "sdd", proyecto_id,
            contenido=f"{base_ctx}\n\nPDD preliminar:\n{pdd}",
        )
        if RelevamientoPipeline._abortar_si_error(proyecto_id, "Gem SDD", sdd):
            return
        ProyectoRepository.guardar_documento(proyecto_id, "SDD", sdd)

        qa = GemsService.invocar(
            "qa", proyecto_id,
            contenido=f"{base_ctx}\n\nPDD:\n{pdd}\n\nSDD:\n{sdd}",
        )
        if RelevamientoPipeline._abortar_si_error(proyecto_id, "Gem QA", qa):
            return
        ProyectoRepository.guardar_documento(proyecto_id, "QA", qa)

        estimacion = GemsService.invocar(
            "estimacion", proyecto_id,
            contenido=f"{base_ctx}\n\nPDD:\n{pdd}\n\nSDD:\n{sdd}\n\nCasos de prueba:\n{qa}",
        )
        if RelevamientoPipeline._abortar_si_error(proyecto_id, "Gem Estimación", estimacion):
            return
        ProyectoRepository.guardar_documento(proyecto_id, "ESTIMACION", estimacion)

        # ── 6) Planificación — Agente Supervisor y Consolidador ─────────
        respuesta_supervisor = GemsService.invocar(
            "supervisor", proyecto_id,
            contenido=(
                "Auditá la consistencia entre los siguientes 4 documentos y respondé "
                'SOLO en JSON con la forma {"consistente": bool, "alertas": ["..."]}.\n\n'
                f"PDD:\n{pdd}\n\nSDD:\n{sdd}\n\nQA:\n{qa}\n\nEstimación:\n{estimacion}"
            ),
        )
        if GemsService.es_error(respuesta_supervisor):
            # el supervisor es el único paso donde, si falla, igual conviene
            # dejar los 4 documentos ya generados disponibles para revisión
            # humana en vez de descartar todo el trabajo previo.
            ProyectoRepository.log(proyecto_id, "Consolidador",
                                    "No se pudo auditar consistencia (falló la Gem Supervisor); "
                                    "los documentos generados quedan disponibles igual.", "warn")
            resultado_supervisor = {"consistente": False, "alertas": []}
        else:
            resultado_supervisor = ConsolidacionService.parsear_respuesta_supervisor(respuesta_supervisor)

        # chequeo determinístico adicional (Regla de Consistencia de Negocio, punto 7)
        resultado_supervisor["alertas"].extend(
            ConsolidacionService.chequear_consistencia_horas(qa, estimacion)
        )

        for alerta in resultado_supervisor["alertas"]:
            ProyectoRepository.agregar_alerta(proyecto_id, "consistencia", alerta)

        nivel = "ok" if resultado_supervisor["consistente"] and not resultado_supervisor["alertas"] else "warn"
        ProyectoRepository.log(
            proyecto_id, "Consolidador",
            f"Auditoría de consistencia: {'sin observaciones' if nivel=='ok' else str(len(resultado_supervisor['alertas'])) + ' alerta(s)'}",
            nivel,
        )

        # ── 7) Acción completada + estado final ─────────────────────────
        ProyectoRepository.actualizar(proyecto_id, {"estado": "completado"})
        ProyectoRepository.log(proyecto_id, "Pipeline",
                                "Paquete documental listo para revisión humana (Evaluación)", "ok")

        # ── 8) Aprendizaje continuo (semilla) ───────────────────────────
        # Registra un antecedente mínimo del proyecto en la memoria de
        # largo plazo. El ajuste fino real ocurre cuando el analista
        # corrige manualmente un documento (ver /api/proyecto/<id>/feedback).
        tags = [t for t in [proyecto.get("tecnologia"), proyecto.get("criticidad")] if t]
        MemoriaService.registrar_aprendizaje(
            proyecto_id, "feedback", tags,
            f"Proyecto '{proyecto['proceso']}' ({proyecto['cliente']}) procesado. "
            f"Alertas de consistencia al cierre: {len(resultado_supervisor['alertas'])}.",
        )

    @staticmethod
    def _abortar_si_error(proyecto_id: int, nombre_paso: str, respuesta: str) -> bool:
        """Si la respuesta de una Gem es un error de conexión (ver
        GemsService.es_error), corta el ciclo acá: marca el proyecto como
        'error' con el detalle real de la falla, en vez de dejar que ese
        texto de error se siga pasando como contenido a las Gems
        siguientes (lo que producía documentos alucinando sobre "no se
        recibió información")."""
        if not GemsService.es_error(respuesta):
            return False
        ProyectoRepository.actualizar(proyecto_id, {
            "estado": "error",
            "motivo_freno": f"{nombre_paso}: {respuesta}",
        })
        ProyectoRepository.log(
            proyecto_id, "Pipeline",
            f"Ciclo interrumpido — {nombre_paso} devolvió un error de conexión con Gemini.",
            "error",
        )
        return True
