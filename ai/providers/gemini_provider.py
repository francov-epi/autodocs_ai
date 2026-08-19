"""Google Gemini Provider — HTTP directo, sin SDK.

Extiende el patrón usado en Wine AI OS agregando soporte de
`system_instruction`, que es lo que permite que una misma clase hable
"como" cualquiera de las Gems del punto 4 (Ingesta, PDD, SDD, QA,
Estimación, Supervisor): cada una es, en definitiva, el mismo modelo
Gemini con una instrucción de sistema distinta.
"""
import requests

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

AVAILABLE_MODELS = [
    {"id": "gemini-3.6-flash",        "label": "Gemini 3.6 Flash — recomendado ★ (Ingesta / QA / Estimación)"},
    {"id": "gemini-3.5-flash-lite",   "label": "Gemini 3.5 Flash-Lite — más rápido/económico"},
    {"id": "gemini-3-pro-preview",    "label": "Gemini 3 Pro (preview) — máx capacidad (Gems documentales)"},
    {"id": "gemini-3.1-pro-preview",  "label": "Gemini 3.1 Pro (preview) — contexto largo / razonamiento"},
]
# Nota (ago-2026): la familia gemini-1.5-* y gemini-2.0-* ya fue dada de baja
# por Google (404 en generateContent); gemini-2.5-* sigue viva pero se apaga
# el 16/10/2026. Si en el momento de leer esto alguno de los IDs de arriba
# también da 404, pedir la lista vigente a
# GET https://generativelanguage.googleapis.com/v1beta/models?key=TU_KEY
# (ListModels) y actualizar esta lista — Google renueva la familia de
# modelos con bastante frecuencia.


class GeminiProvider:

    # Timeout por defecto para la llamada HTTP a Gemini. Los modelos
    # *-pro-preview (usados por PDD/SDD) son modelos "de razonamiento": el
    # tiempo de respuesta varía mucho más que en un modelo flash y 120s
    # queda corto seguido, sobre todo con documentos/transcripciones
    # largas — de ahí el "Read timed out" aunque el prompt pida respuestas
    # acotadas (esa instrucción reduce el texto de salida, pero no el
    # tiempo de "pensado" interno del modelo antes de responder).
    DEFAULT_TIMEOUT = 300

    def __init__(self, config: dict):
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "gemini-3.6-flash")
        self.timeout = config.get("timeout", self.DEFAULT_TIMEOUT)

    def analyze(self, prompt: str, system_instruction: str = "", response_json: bool = False,
                response_schema: dict = None, max_output_tokens: int = None,
                timeout: int = None, reintentos: int = 1) -> str:
        """Llama a la API de Gemini. `system_instruction` es el prompt del
        Gem correspondiente (definido/editado en /configuracion); `prompt`
        es el contenido variable de la llamada (transcripción, flujo
        estructurado, PDD preliminar, etc.).

        `response_json=True` activa el modo de salida estructurada nativo
        de Gemini (generationConfig.responseMimeType=application/json): el
        modelo queda restringido a devolver únicamente JSON válido.

        `response_schema`, cuando se provee, va un paso más allá: fuerza
        además la FORMA exacta del JSON (nombres de campo y tipos), vía
        generationConfig.responseSchema. Solo con responseMimeType el
        modelo puede devolver JSON válido pero con su propia estructura
        inventada (nombres de campo distintos a los que el parser espera)
        — responseSchema elimina ese margen.

        `max_output_tokens`, cuando se provee, fija un tope DURO de
        longitud de respuesta (generationConfig.maxOutputTokens). A
        diferencia de pedirle por prompt "no más de dos párrafos" —que el
        modelo puede no respetar al pie de la letra—, este parámetro corta
        la generación de forma determinística y además reduce el tiempo
        total de respuesta, que es lo que más ayuda a evitar el timeout.

        `timeout`/`reintentos`: permiten override puntual del timeout y la
        cantidad de reintentos ante un timeout de red (por defecto 1
        reintento con el mismo timeout, útil para hiccups transitorios de
        la red; no reintenta ante errores HTTP como 4xx/5xx, solo ante
        timeout de lectura/conexión)."""
        if not self.api_key:
            return "⚠ Gemini: API key no configurada. Ve a Configuración."

        url = f"{BASE_URL}/{self.model}:generateContent?key={self.api_key}"
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        generation_config = {}
        if response_schema:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = response_schema
        elif response_json:
            generation_config["responseMimeType"] = "application/json"
        if max_output_tokens:
            generation_config["maxOutputTokens"] = max_output_tokens
        if generation_config:
            body["generationConfig"] = generation_config

        timeout_efectivo = timeout or self.timeout
        intentos_restantes = max(1, reintentos + 1)
        ultimo_error = None
        while intentos_restantes > 0:
            try:
                r = requests.post(url, json=body, timeout=timeout_efectivo)
                r.raise_for_status()
                return (r.json()
                        .get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "Sin respuesta"))
            except requests.HTTPError as e:
                detail = ""
                try:
                    detail = e.response.json().get("error", {}).get("message", "")
                except Exception:
                    pass
                return f"❌ Gemini HTTP {e.response.status_code}: {detail or str(e)}"
            except (requests.Timeout, requests.ConnectionError) as e:
                ultimo_error = e
                intentos_restantes -= 1
                if intentos_restantes <= 0:
                    return (
                        f"❌ Error de red hacia Gemini: {str(e)} "
                        f"(timeout={timeout_efectivo}s). Si esto se repite seguido con "
                        f"un modelo *-pro-preview, considerá subir el timeout del "
                        f"provider en /configuracion o bajar el largo esperado de "
                        f"respuesta (maxOutputTokens) para esa Gem."
                    )
                # reintento simple ante timeout/hiccup de red transitorio
            except requests.RequestException as e:
                return f"❌ Error de red hacia Gemini: {str(e)}"
        return f"❌ Error de red hacia Gemini: {str(ultimo_error)}"

    def list_models(self) -> dict:
        """Consulta en vivo ListModels para saber qué modelos están
        habilitados hoy para esta API key (evita depender de una lista
        hardcodeada que Google puede volver a cambiar)."""
        if not self.api_key:
            return {"ok": False, "message": "API key no configurada.", "models": []}
        url = f"{BASE_URL}?key={self.api_key}"
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            data = r.json().get("models", [])
            disponibles = [
                m["name"].replace("models/", "")
                for m in data
                if "generateContent" in m.get("supportedGenerationMethods", [])
            ]
            return {"ok": True, "message": f"{len(disponibles)} modelos disponibles.", "models": disponibles}
        except requests.RequestException as e:
            return {"ok": False, "message": f"Error consultando ListModels: {e}", "models": []}

    def test(self) -> dict:
        result = self.analyze("Responde solo 'OK'.")
        ok = "ok" in result.lower() and "❌" not in result and "⚠" not in result
        return {"ok": ok, "message": result}
