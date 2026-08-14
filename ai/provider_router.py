from ai.providers.gemini_provider import GeminiProvider

# El Trabajo de Medio Ciclo fija a la familia Gemini como motor de las Gems
# (punto 4 y stack tecnológico). El router se deja igual de extensible que
# en Wine AI OS por si en el futuro se suma otro proveedor, pero hoy solo
# resuelve Gemini.
_CLASSES = {
    "gemini": GeminiProvider,
}


class ProviderRouter:

    @staticmethod
    def get_provider(config: dict, provider_name: str = None):
        name = (provider_name or config.get("provider", "gemini")).lower()
        cls = _CLASSES.get(name, GeminiProvider)
        pcfg = config.get("providers", {}).get(name, {})
        return cls(pcfg)

    @staticmethod
    def available() -> list:
        return list(_CLASSES.keys())
