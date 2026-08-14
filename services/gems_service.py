"""
GemsService — capa de CONEXIÓN con el pool de Gems del punto 4.

Deliberadamente NO contiene la lógica/razonamiento de ningún Gem (Ingesta,
PDD, SDD, QA, Estimación, Supervisor): esa inteligencia se diseña y se
mantiene directamente en Gemini, como Gem propiamente dicha, y se referencia
acá solo por su `system_instruction` (configurable en /configuracion).

Lo que sí resuelve este módulo:
  - armar el payload que le corresponde a cada Gem (contexto + memoria
    relevante + parámetros del proyecto),
  - invocar al proveedor (GeminiProvider) con el modelo y la instrucción
    de sistema configurados para esa Gem,
  - dejar traza en `logs_agenticos` para que el dashboard de Procesamiento
    (Figura 4 del enunciado) pueda mostrar el log de comunicación agéntica,
  - devolver el texto crudo de la Gem para que el pipeline lo persista.
"""
from core.config_manager import ConfigManager
from ai.provider_router import ProviderRouter
from repositories.proyecto_repository import ProyectoRepository


class GemsService:

    @staticmethod
    def invocar(gem_key: str, proyecto_id: int, contenido: str, etiqueta_log: str = None) -> str:
        """Invoca a la Gem `gem_key` (ver DEFAULTS['gems'] en config_manager)
        pasándole `contenido` como entrada variable. Registra la llamada en
        el log agéntico del proyecto."""
        cfg = ConfigManager.load()
        gem_cfg = cfg["gems"].get(gem_key)
        if not gem_cfg:
            raise ValueError(f"Gem desconocida: {gem_key}")

        nombre = etiqueta_log or gem_cfg.get("nombre", gem_key)
        provider = ProviderRouter.get_provider(
            {"provider": "gemini", "providers": cfg["providers"]}, "gemini"
        )
        # el modelo puede variar por Gem (ej. Pro para PDD/SDD, Flash para QA/Estimación)
        provider.model = gem_cfg.get("model", provider.model)

        ProyectoRepository.log(proyecto_id, nombre, "consultando…", nivel="info")
        respuesta = provider.analyze(
            prompt=contenido,
            system_instruction=gem_cfg.get("system_instruction", ""),
        )
        nivel = "error" if respuesta.startswith(("❌", "⚠")) else "ok"
        ProyectoRepository.log(proyecto_id, nombre, "respuesta recibida", nivel=nivel)
        return respuesta

    @staticmethod
    def listar_modelos_disponibles() -> dict:
        """Modelos habilitados hoy para la API key configurada (ListModels
        en vivo), para no depender de una lista hardcodeada en el código
        que Google puede volver a dar de baja."""
        cfg = ConfigManager.load()
        provider = ProviderRouter.get_provider(
            {"provider": "gemini", "providers": cfg["providers"]}, "gemini"
        )
        return provider.list_models()

    @staticmethod
    def probar_conexion() -> dict:
        """Prueba la conexión genérica con Gemini (usada en /configuracion)."""
        cfg = ConfigManager.load()
        provider = ProviderRouter.get_provider(
            {"provider": "gemini", "providers": cfg["providers"]}, "gemini"
        )
        result = provider.test()
        result["provider"] = "gemini"
        return result
