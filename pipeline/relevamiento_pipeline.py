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
        # mismo nodo de "Análisis" del ciclo.
        base_ctx = (
            f"Cliente: {proyecto['cliente']}\nProceso: {proyecto['proceso']}\n"
            f"Tecnología objetivo: {proyecto.get('tecnologia') or 'no especificada'}\n"
            f"Criticidad: {proyecto.get('criticidad') or 'no especificada'}\n"
            f"Presupuesto estimado (hs): {proyecto.get('presupuesto_hs') or 'no especificado'}\n\n"
            f"Flujo estructurado (Gem Ingesta):\n{flujo}\n\n{memoria_ctx}"
        )

        pdd = GemsService.invocar("pdd", proyecto_id, contenido=base_ctx)
        ProyectoRepository.guardar_documento(proyecto_id, "PDD", pdd)

        sdd = GemsService.invocar(
            "sdd", proyecto_id,
            contenido=f"{base_ctx}\n\nPDD preliminar:\n{pdd}",
        )
        ProyectoRepository.guardar_documento(proyecto_id, "SDD", sdd)

        qa = GemsService.invocar(
            "qa", proyecto_id,
            contenido=f"{base_ctx}\n\nPDD:\n{pdd}\n\nSDD:\n{sdd}",
        )
        ProyectoRepository.guardar_documento(proyecto_id, "QA", qa)

        estimacion = GemsService.invocar(
            "estimacion", proyecto_id,
            contenido=f"{base_ctx}\n\nPDD:\n{pdd}\n\nSDD:\n{sdd}\n\nCasos de prueba:\n{qa}",
        )
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
