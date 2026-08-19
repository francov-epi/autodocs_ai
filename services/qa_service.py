"""
QaService — interpreta la respuesta JSON de la Gem QA (ver
system_instruction en config_manager). Mismo criterio de tolerancia que
PddService/SddService/EstimacionService.

La numeración de casos (CP001, CP002...) la asigna este módulo, no la Gem:
así queda consistente aunque la Gem no numere bien o reordene casos en una
edición conversacional posterior.
"""
import json
import re

_ESQUELETO_VACIO = {"modulo_general": "", "casos": []}


class QaService:

    @staticmethod
    def parsear(texto_respuesta: str) -> dict:
        limpio = re.sub(r"^```(?:json)?|```$", "", texto_respuesta.strip(), flags=re.MULTILINE).strip()

        data = None
        try:
            data = json.loads(limpio)
        except (json.JSONDecodeError, TypeError):
            match = re.search(r"\{.*\}", texto_respuesta, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except (json.JSONDecodeError, TypeError):
                    data = None

        if not isinstance(data, dict):
            esqueleto = json.loads(json.dumps(_ESQUELETO_VACIO))
            esqueleto["modulo_general"] = (
                "⚠ La Gem no devolvió JSON válido, se muestra la respuesta cruda: "
                + texto_respuesta[:2000]
            )
            return esqueleto

        data.setdefault("modulo_general", "")
        data.setdefault("casos", [])
        if not isinstance(data["casos"], list):
            data["casos"] = []

        for i, caso in enumerate(data["casos"], start=1):
            if isinstance(caso, dict):
                caso["numero"] = f"CP{i:03d}"
                caso.setdefault("version", "1.0")

        return data

    @staticmethod
    def resumen_legible(data: dict) -> str:
        """Texto corto para la pestaña de Resultados, sin volcar el JSON crudo."""
        casos = data.get("casos", [])
        lineas = [f"QA — {data.get('modulo_general') or '(sin nombre)'}", "",
                  f"Casos de prueba generados: {len(casos)}"]
        positivos = sum(1 for c in casos if isinstance(c, dict) and c.get("tipo", "").lower().startswith("posit"))
        negativos = sum(1 for c in casos if isinstance(c, dict) and c.get("tipo", "").lower().startswith("negat"))
        if casos:
            lineas.append(f"  · Positivos: {positivos} · Negativos: {negativos}")
            lineas.append("")
            for c in casos:
                if isinstance(c, dict):
                    lineas.append(f"- {c.get('numero','')} · {c.get('nombre_caso','')} ({c.get('criticidad','—')})")
        return "\n".join(lineas)
