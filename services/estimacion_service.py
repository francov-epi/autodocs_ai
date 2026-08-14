"""
EstimacionService — interpreta la respuesta de la Gem Estimación.

La Gem devuelve JSON (ver system_instruction en config_manager). Este
módulo la parsea de forma tolerante: los LLM a veces envuelven el JSON en
```json ... ``` o agregan una frase antes/después a pesar de que se les pida
que no lo hagan. Si el parseo falla igual, se devuelve un esqueleto vacío
con el texto crudo adentro de 'otras_consideraciones' para no perder la
respuesta ni romper la exportación a Excel.
"""
import json
import re

FASES_ESPERADAS = [
    "Relevamiento", "Análisis y Diseño", "Desarrollo",
    "Pruebas", "Ajustes", "Documentación", "Gestión",
]

_ESQUELETO_VACIO = {
    "proceso": "",
    "fases": [{"fase": f, "task": f, "entregable": "", "responsable": "", "horas": 0}
              for f in FASES_ESPERADAS],
    "detalle_desarrollo": [],
    "otras_consideraciones": "",
    "supuestos": [],
    "preguntas_abiertas": [],
}


class EstimacionService:

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
            esqueleto["otras_consideraciones"] = (
                "⚠ La Gem no devolvió JSON válido, se muestra la respuesta cruda: "
                + texto_respuesta[:2000]
            )
            return esqueleto

        data.setdefault("proceso", "")
        data.setdefault("fases", [])
        data.setdefault("detalle_desarrollo", [])
        data.setdefault("otras_consideraciones", "")
        data.setdefault("supuestos", [])
        data.setdefault("preguntas_abiertas", [])

        # completar fases faltantes con horas 0 para no romper el template fijo
        fases_presentes = {f.get("fase") for f in data["fases"] if isinstance(f, dict)}
        for nombre_fase in FASES_ESPERADAS:
            if nombre_fase not in fases_presentes:
                data["fases"].append({"fase": nombre_fase, "task": nombre_fase,
                                       "entregable": "", "responsable": "", "horas": 0})

        # la fase "Desarrollo" siempre se recalcula desde el detalle
        horas_desarrollo = sum(
            EstimacionService._num(t.get("horas")) for t in data["detalle_desarrollo"]
            if isinstance(t, dict)
        )
        for f in data["fases"]:
            if isinstance(f, dict) and f.get("fase") == "Desarrollo":
                f["horas"] = horas_desarrollo

        return data

    @staticmethod
    def _num(v) -> float:
        try:
            return float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def horas_totales(data: dict) -> float:
        return sum(EstimacionService._num(f.get("horas")) for f in data.get("fases", [])
                   if isinstance(f, dict))

    @staticmethod
    def resumen_legible(data: dict) -> str:
        """Texto corto para mostrar en la pestaña de Resultados sin volcar el JSON crudo."""
        total = EstimacionService.horas_totales(data)
        lineas = [f"Estimación total: {total:.0f} hs (~{total/6:.1f} días hábiles de 6hs)", ""]
        for f in data.get("fases", []):
            if isinstance(f, dict):
                lineas.append(f"- {f.get('fase')}: {EstimacionService._num(f.get('horas')):.0f} hs — {f.get('task','')}")
        if data.get("supuestos"):
            lineas.append("\nSupuestos:")
            lineas += [f"  · {s}" for s in data["supuestos"]]
        if data.get("preguntas_abiertas"):
            lineas.append("\nPreguntas abiertas:")
            lineas += [f"  · {s}" for s in data["preguntas_abiertas"]]
        if data.get("otras_consideraciones"):
            lineas.append(f"\nOtras consideraciones: {data['otras_consideraciones']}")
        return "\n".join(lineas)
