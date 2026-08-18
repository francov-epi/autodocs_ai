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


_SDD_OUTPUT_CONTRACT = r"""
REGLA INVIOLABLE DE SALIDA PARA SDD:
La respuesta DEBE ser exclusivamente un objeto JSON válido que cumpla exactamente el esquema SDD configurado en la aplicación.
NO uses seccion_1, seccion_2, seccion_3, indice, titulo_documento, nombre_bot, proyecto, cliente, mes_anio, diagramas, documento, data ni ninguna clave adicional.
NO devuelvas un objeto contenedor. Todas las claves del esquema deben estar en la raíz.
NO conviertas ninguna lista de objetos en texto. Mantén exactamente arrays de objetos para packages, archivos_flujo, recursos_externos y glosario.
Para campos escalares como objetivos, como_empezar, ambiente_produccion, datos_entrada, datos_salida y reportes, devuelve SIEMPRE un string, nunca un objeto ni un array.
En particular, como_empezar debe contener SOLO cómo se dispara/inicia el proceso automático. Las aplicaciones usadas NO deben colocarse dentro de como_empezar.
Si informas aplicaciones usadas, inclúyelas en ambiente_produccion como texto legible o usa la información para completar los campos correspondientes; nunca generes objetos con claves aplicacion/environment_access dentro de campos escalares.
objetivos debe describir el objetivo de la automatización; NO debe contener las listas "dentro_alcance" ni "fuera_alcance".
No serialices objetos como texto con formato Python del tipo {'clave': 'valor'} ni como JSON dentro de strings.
Si un dato no está disponible, devuelve "" (o [] cuando el campo sea una lista), no inventes ni cambies el tipo.
"""


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
        system_instruction = gem_cfg.get("system_instruction", "")
        # El contrato SDD se aplica siempre desde la aplicación, incluso si
        # existe una configuración persistida antigua de la Gem. Así evitamos
        # que un prompt viejo vuelva a introducir seccion_1/diagramas/etc.
        if gem_key == "sdd":
            system_instruction = system_instruction.rstrip() + "\n\n" + _SDD_OUTPUT_CONTRACT

        respuesta = provider.analyze(
            prompt=contenido,
            system_instruction=system_instruction,
            response_json=(gem_key == "sdd" or gem_cfg.get("output_format") == "json"),
        )
        if GemsService.es_error(respuesta):
            ProyectoRepository.log(proyecto_id, nombre, f"error: {respuesta[:300]}", nivel="error")
        else:
            ProyectoRepository.log(proyecto_id, nombre, "respuesta recibida", nivel="ok")
        return respuesta

    @staticmethod
    def es_error(respuesta: str) -> bool:
        """GeminiProvider.analyze devuelve el error como texto plano (nunca
        levanta excepción) prefijado con ❌ (error HTTP/red) o ⚠ (falta la
        API key). Este helper lo detecta para que el pipeline pueda cortar
        el ciclo en vez de seguir pasando ese texto como si fuera la
        respuesta real de la Gem a los pasos siguientes."""
        return isinstance(respuesta, str) and respuesta.startswith(("❌", "⚠"))

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
