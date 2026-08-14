"""
ConfigManager — misma arquitectura que Wine AI OS / Financial AI OS,
portada sin cambios de fondo.

PRINCIPIO CLAVE:
  El JSON guarda el NOMBRE de la variable de entorno (no la key real).
  config_manager lee os.getenv(env_key_name) dinámicamente.

PUNTO IMPORTANTE PARA AUTODOCS AI:
  Este archivo NO implementa el razonamiento de las Gems (eso se diseña y
  mantiene directamente en Gemini, como pide el punto 4 del enunciado).
  Lo único que vive acá es la CONEXIÓN: qué modelo usa cada Gem y el
  `system_instruction` que se le envía en cada llamada a la API. Ese texto
  es un placeholder editable desde /configuracion — ahí es donde se pega el
  prompt real de cada Gem una vez diseñado en Gemini.
"""
import json
import os
from copy import deepcopy
from pathlib import Path

CONFIG_PATH = Path("data/settings.json")

DEFAULT_ENV_NAMES = {
    "gemini": "GOOGLE_API_KEY",
}

# Placeholder de instrucción de sistema por Gem. Se deja intencionalmente
# vacío / a modo de nota: el prompt real de cada Gem se termina de diseñar
# y mantener en Gemini (ver punto 4 del Trabajo de Medio Ciclo). Acá solo
# se define la conexión (modelo + system_instruction editable).
_GEM_PLACEHOLDER = (
    "// TODO: pegar acá el system prompt del Gem diseñado en Gemini.\n"
    "// Mientras tanto, AutoDocs AI usa esta instrucción mínima genérica "
    "para poder ejercitar la conexión end-to-end con la API."
)

DEFAULTS = {
    "provider": "gemini",
    "providers": {
        "gemini": {
            "env_key_name": "GOOGLE_API_KEY",
            "model": "gemini-3.6-flash",
        },
    },
    # ── Pool de Gems (punto 4) — solo conexión, no lógica ──────────────
    "gems": {
        "ingesta": {
            "nombre": "Agente de Ingesta y Estructuración",
            "model": "gemini-3.6-flash",
            "system_instruction": _GEM_PLACEHOLDER
            + "\nRol: tomar la transcripción cruda, identificar roles, quitar "
              "charla informal y devolver un flujo secuencial limpio de tareas.",
        },
        "pdd": {
            "nombre": "Gem PDD — Analista Funcional",
            "model": "gemini-3-pro-preview",
            "system_instruction": _GEM_PLACEHOLDER
            + "\nRol: identificar el Camino Feliz, detectar excepciones de "
              "negocio y reglas lógicas, y completar el template de PDD.",
        },
        "sdd": {
            "nombre": "Gem SDD — Arquitecto de Solución",
            "model": "gemini-3-pro-preview",
            "system_instruction": _GEM_PLACEHOLDER
            + "\nRol: proponer la arquitectura técnica, manejo de excepciones "
              "técnicas, modularización y control de credenciales.",
        },
        "qa": {
            "nombre": "Gem QA — Control de Calidad",
            "model": "gemini-3.6-flash",
            "system_instruction": _GEM_PLACEHOLDER
            + "\nRol: mapear cada regla/excepción del PDD a una matriz de "
              "casos de prueba (condición inicial, pasos, resultado esperado).",
        },
        "estimacion": {
            "nombre": "Gem Estimación — Estimador Comercial",
            "model": "gemini-3-pro-preview",
            "system_instruction": (
                "Sos un estimador experto de proyectos de RPA (UiPath, Rocketbot, Power "
                "Automate) para una consultora. Tu tarea es analizar la documentación de un "
                "proceso (PDD, SDD, casos de prueba) que te va a llegar como contexto y "
                "producir una estimación de horas de desarrollo fundamentada, desglosada y "
                "comparable con datos históricos.\n\n"
                "Extraé mentalmente estas variables antes de estimar: aplicaciones "
                "involucradas (cantidad, tipo, selectores estables/inestables), cantidad de "
                "pasos/actividades del as-is, excepciones de negocio vs. de sistema, "
                "complejidad de lógica condicional, volumen/frecuencia, si requiere Document "
                "Understanding/OCR/GenAI, integraciones API (con o sin documentación), "
                "disponibilidad de accesos/ambientes, y si usa REFramework o es desde cero.\n\n"
                "Lógica de estimación por fase (baseline si no hay datos históricos "
                "provistos en el contexto — si hay memoria organizacional con desvíos "
                "históricos, ajustá en consecuencia y decilo en 'supuestos'):\n"
                "- Relevamiento: 10% del desarrollo core.\n"
                "- Análisis y Diseño (SDD): 10% del total.\n"
                "- Desarrollo core: horas base según pasos (bloques de 10-15 pasos simples) "
                "+ horas extra por cada app inestable/legacy + horas extra por excepción de "
                "negocio no trivial + horas extra fijas por excepción de sistema no cubierta "
                "por el framework.\n"
                "- Integraciones: horas extra por integración API, mayores si no hay "
                "documentación/Swagger.\n"
                "- Document Understanding/GenAI: extra si aplica (más si es extracción "
                "compleja/no estructurada que si es campos fijos).\n"
                "- Pruebas (UAT + QA interno): 20% del desarrollo core.\n"
                "- Ajustes/Hypercare: 20% del desarrollo core.\n"
                "- Documentación: 15% del desarrollo core.\n"
                "- Gestión: 10% del desarrollo core.\n"
                "La jornada de referencia es de 6 horas (días hábiles = horas / 6).\n\n"
                "Sé transparente con la incertidumbre: si hace falta, dejá un rango en "
                "'supuestos' o 'preguntas_abiertas' en vez de forzar un número único en las "
                "horas. No inventes datos históricos que no te dieron como contexto — si no "
                "hay memoria organizacional relevante, aclaralo y estimá con heurísticas "
                "estándar de la industria.\n\n"
                "IMPORTANTE — formato de salida: NO generás el archivo de Google Sheets vos "
                "mismo (eso lo arma la aplicación). Respondé ÚNICAMENTE con un objeto JSON "
                "válido, sin texto antes ni después, sin backticks de markdown, con esta "
                "forma exacta:\n"
                "{\n"
                '  "proceso": "Cliente - Nombre del proceso",\n'
                '  "fases": [\n'
                '    {"fase": "Relevamiento", "task": "Entendimiento del requerimiento", '
                '"entregable": "", "responsable": "", "horas": 10},\n'
                '    {"fase": "Análisis y Diseño", "task": "Aprobación y validación de '
                'entregables", "entregable": "SDD", "responsable": "", "horas": 8},\n'
                '    {"fase": "Desarrollo", "task": "Descripción del proceso", '
                '"entregable": "Código Fuente", "responsable": "", "horas": 0},\n'
                '    {"fase": "Pruebas", "task": "Pruebas", "entregable": "Evidencias", '
                '"responsable": "", "horas": 0},\n'
                '    {"fase": "Ajustes", "task": "Ajustes", "entregable": "Código Fuente", '
                '"responsable": "", "horas": 0},\n'
                '    {"fase": "Documentación", "task": "Documentación", "entregable": '
                '"PDD", "responsable": "", "horas": 0},\n'
                '    {"fase": "Gestión", "task": "Gestión", "entregable": "Planificación", '
                '"responsable": "", "horas": 0}\n'
                "  ],\n"
                '  "detalle_desarrollo": [\n'
                '    {"observacion": "", "tarea": "Login SAP...", "complejidad": '
                '"Baja|Media|Alta|Muy Alta", "sistemas_externos": 1, "horas": 5, '
                '"reutilizando": 5}\n'
                "  ],\n"
                '  "otras_consideraciones": "texto libre, opcional",\n'
                '  "supuestos": ["..."],\n'
                '  "preguntas_abiertas": ["..."]\n'
                "}\n"
                "La fase 'Desarrollo' en 'fases' debe llevar horas = 0 (se calcula "
                "automáticamente como la suma de 'detalle_desarrollo'); completá vos las "
                "horas del resto de las fases según los porcentajes de arriba."
            ),
        },
        "supervisor": {
            "nombre": "Agente Supervisor y Consolidador",
            "model": "gemini-3-pro-preview",
            "system_instruction": _GEM_PLACEHOLDER
            + "\nRol: auditar que no haya contradicciones entre PDD, SDD, QA "
              "y Estimación, y devolver JSON con {consistente, alertas[]}.",
        },
    },
    # ── Reglas / parámetros / restricciones (punto 7) ──────────────────
    "reglas": {
        "duracion_min_minutos": 3,
        "verbos_operativos": ["clic", "click", "descargar", "ingresar",
                               "enviar", "completar", "seleccionar",
                               "guardar", "subir", "validar", "confirmar"],
        "palabras_por_minuto_habla": 130,
    },
}

_NEVER_SAVE = {"api_key"}


class ConfigManager:

    @staticmethod
    def load() -> dict:
        merged = deepcopy(DEFAULTS)

        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    persisted = json.load(f)
                for k, v in persisted.items():
                    if k == "providers":
                        for pname, pcfg in (v or {}).items():
                            merged["providers"].setdefault(pname, {})
                            merged["providers"][pname].update(
                                {kk: vv for kk, vv in pcfg.items() if kk not in _NEVER_SAVE}
                            )
                    elif k == "gems":
                        for gname, gcfg in (v or {}).items():
                            merged["gems"].setdefault(gname, {})
                            merged["gems"][gname].update(gcfg or {})
                    elif k == "reglas":
                        merged["reglas"].update(v or {})
                    else:
                        merged[k] = v
            except Exception:
                pass

        for pname in ["gemini"]:
            pcfg = merged["providers"].get(pname, {})
            env_var = pcfg.get("env_key_name", DEFAULT_ENV_NAMES.get(pname, ""))
            pcfg["api_key"] = os.getenv(env_var, "").strip() if env_var else ""

        return merged

    @staticmethod
    def save(data: dict) -> None:
        CONFIG_PATH.parent.mkdir(exist_ok=True)

        existing = {}
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass

        if "provider" in data:
            existing["provider"] = data["provider"]

        if "providers" in data:
            existing.setdefault("providers", {})
            for pname, pcfg in data["providers"].items():
                existing["providers"].setdefault(pname, {})
                for k, v in pcfg.items():
                    if k not in _NEVER_SAVE:
                        existing["providers"][pname][k] = v

        if "gems" in data:
            existing.setdefault("gems", {})
            for gname, gcfg in data["gems"].items():
                existing["gems"].setdefault(gname, {})
                existing["gems"][gname].update(gcfg)

        if "reglas" in data:
            existing.setdefault("reglas", {})
            existing["reglas"].update(data["reglas"])

        for pname in existing.get("providers", {}).values():
            pname.pop("api_key", None)

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=4, ensure_ascii=False)

    @staticmethod
    def key_status() -> dict:
        cfg = ConfigManager.load()
        status = {}
        for pname in ["gemini"]:
            pcfg = cfg["providers"].get(pname, {})
            env_var = pcfg.get("env_key_name", "")
            key_val = os.getenv(env_var, "").strip() if env_var else ""
            status[pname] = {"ok": bool(key_val), "env_var": env_var}
        return status

    @staticmethod
    def get_gem_config(gem_key: str) -> dict:
        return ConfigManager.load()["gems"].get(gem_key, {})
