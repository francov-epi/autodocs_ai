"""
ConsolidacionService — apoya al Agente Supervisor y Consolidador.

La lógica de auditoría en sí (¿el PDD y el SDD son consistentes? ¿cada
excepción de negocio tiene su caso de prueba?) la resuelve la Gem
"supervisor" en Gemini. Este módulo solo sabe interpretar de forma robusta
la respuesta de esa Gem (se le pide JSON, pero conviene no romper el
pipeline si devuelve texto libre) y aplicar la Regla de Consistencia de
Negocio del punto 7 como chequeo determinístico adicional, no reemplazable
por IA: ninguna estimación puede aprobarse si los casos de prueba de alta
complejidad no tienen impacto proporcional en las horas asignadas.
"""
import json
import re


class ConsolidacionService:

    @staticmethod
    def parsear_respuesta_supervisor(texto_respuesta: str) -> dict:
        """Intenta parsear {"consistente": bool, "alertas": [str, ...]}.
        Si la Gem no devolvió JSON válido, degrada a una sola alerta con el
        texto crudo para no perder la señal."""
        match = re.search(r"\{.*\}", texto_respuesta, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                return {
                    "consistente": bool(data.get("consistente", False)),
                    "alertas": list(data.get("alertas", [])),
                }
            except (json.JSONDecodeError, TypeError):
                pass
        return {"consistente": False, "alertas": [texto_respuesta.strip()]}

    @staticmethod
    def chequear_consistencia_horas(qa_texto: str, estimacion_texto: str) -> list:
        """Chequeo determinístico de la Regla de Consistencia de Negocio:
        si QA menciona 'alta complejidad' pero la Estimación no refleja
        horas proporcionalmente altas, se levanta una alerta. Heurístico
        y complementario al análisis de la Gem Supervisor, no un reemplazo."""
        alertas = []
        menciona_alta_complejidad = "alta complejidad" in (qa_texto or "").lower()
        horas_detectadas = re.findall(r"(\d+(?:[.,]\d+)?)\s*h(?:s|oras)?\b",
                                       (estimacion_texto or "").lower())
        horas_max = max((float(h.replace(",", ".")) for h in horas_detectadas), default=0)

        if menciona_alta_complejidad and horas_max and horas_max < 8:
            alertas.append(
                "Se detectaron casos de prueba de alta complejidad técnica, pero la "
                "estimación no parece reflejar un impacto proporcional en las horas "
                "(regla de consistencia de negocio, punto 7)."
            )
        return alertas
