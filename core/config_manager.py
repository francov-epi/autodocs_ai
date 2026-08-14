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
            "model": "gemini-3.6-flash",
            "system_instruction": _GEM_PLACEHOLDER
            + "\nRol: calcular horas sugeridas según apps involucradas, "
              "pasos, tipos de excepciones y datos históricos de memoria.",
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
