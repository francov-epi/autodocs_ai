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

    def __init__(self, config: dict):
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "gemini-3.6-flash")

    def analyze(self, prompt: str, system_instruction: str = "", response_json: bool = False) -> str:
        """Llama a la API de Gemini. `system_instruction` es el prompt del
        Gem correspondiente (definido/editado en /configuracion); `prompt`
        es el contenido variable de la llamada (transcripción, flujo
        estructurado, PDD preliminar, etc.). `response_json=True` activa el
        modo de salida estructurada nativo de Gemini (generationConfig.
        responseMimeType=application/json): el modelo queda restringido a
        devolver únicamente JSON válido, en vez de confiar solo en que la
        instrucción de texto alcance para evitar que agregue markdown,
        tablas en texto o diagramas ASCII alrededor de la respuesta."""
        if not self.api_key:
            return "⚠ Gemini: API key no configurada. Ve a Configuración."

        url = f"{BASE_URL}/{self.model}:generateContent?key={self.api_key}"
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if response_json:
            body["generationConfig"] = {"responseMimeType": "application/json"}

        try:
            r = requests.post(url, json=body, timeout=120)
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
        except requests.RequestException as e:
            return f"❌ Error de red hacia Gemini: {str(e)}"

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
