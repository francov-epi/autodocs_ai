"""
PddService — interpreta la respuesta JSON de la Gem PDD (ver
system_instruction en config_manager). Mismo criterio de tolerancia que
EstimacionService: si el LLM envuelve el JSON en ```json o agrega texto
alrededor, se limpia; si el parseo falla igual, se degrada a un esqueleto
con el texto crudo en 'descripcion_breve' para no perder la respuesta.
"""
import json
import re

_ESQUELETO_VACIO = {
    "nombre_proceso": "", "area_proceso": "", "area": "", "descripcion_breve": "",
    "objetivos": "", "roles_aplicaciones": "", "horario_frecuencia": "",
    "veces_ejecucion": "", "tiempo_ejecucion": "", "restricciones": "",
    "periodo_pico": "", "volumen_pico": "", "personas_proceso": "",
    "datos_entrada": "", "datos_salida": "",
    "aplicaciones": [], "camino_feliz": [], "dentro_alcance": [], "fuera_alcance": [],
    "excepciones_negocio_conocidas": [], "excepciones_negocio_desconocidas": "",
    "errores_sistema_conocidos": [], "errores_sistema_desconocidos": "",
    "reportes": [], "supuestos": [], "preguntas_abiertas": [],
}


class PddService:

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
            esqueleto["descripcion_breve"] = (
                "⚠ La Gem no devolvió JSON válido, se muestra la respuesta cruda: "
                + texto_respuesta[:2000]
            )
            return esqueleto

        for k, v in _ESQUELETO_VACIO.items():
            data.setdefault(k, v)
        return data

    @staticmethod
    def resumen_legible(data: dict) -> str:
        """Texto corto para la pestaña de Resultados, sin volcar el JSON crudo."""
        lineas = [f"PDD — {data.get('nombre_proceso') or '(sin nombre)'}", ""]
        if data.get("descripcion_breve"):
            lineas.append(data["descripcion_breve"])
        lineas.append(f"\nCamino Feliz: {len(data.get('camino_feliz', []))} paso(s)")
        lineas.append(f"Excepciones de negocio conocidas: {len(data.get('excepciones_negocio_conocidas', []))}")
        lineas.append(f"Errores de sistema conocidos: {len(data.get('errores_sistema_conocidos', []))}")
        if data.get("supuestos"):
            lineas.append("\nSupuestos:")
            lineas += [f"  · {s}" for s in data["supuestos"]]
        if data.get("preguntas_abiertas"):
            lineas.append("\nPreguntas abiertas:")
            lineas += [f"  · {s}" for s in data["preguntas_abiertas"]]
        return "\n".join(lineas)
