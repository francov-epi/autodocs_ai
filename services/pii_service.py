"""
PiiService — Restricción de Seguridad y Privacidad (punto 7): antes de que
la transcripción llegue a cualquier Gem, se sanitizan contraseñas, tokens y
datos sensibles del cliente, sustituyéndolos por [MOCK_DATA] o
[SISTEMA_COMPARTIDO] según corresponda.

Es una sanitización heurística por expresiones regulares — suficiente para
la demo/conexión; en un entorno productivo conviene reforzarla con un
detector de PII dedicado (ej. Presidio) antes de enviar contenido a Gemini.
"""
import re

# credenciales / tokens explícitos → [MOCK_DATA]
_PATRONES_MOCK = [
    re.compile(r"(contrase[ñn]a|password|pass|pwd)\s*[:=]?\s*\S+", re.IGNORECASE),
    re.compile(r"\b(token|api[_\s-]?key|secret)\s*[:=]?\s*[\w\-\.]{6,}", re.IGNORECASE),
    re.compile(r"\b\d{2}[.\-]?\d{3}[.\-]?\d{3}\b"),  # DNI (AR)
    re.compile(r"[\w\.-]+@[\w\.-]+\.\w+"),           # emails
]

# nombres de sistemas internos compartidos mencionados junto a credenciales
# → [SISTEMA_COMPARTIDO] (heurística simple: "usuario compartido de <X>")
_PATRON_SISTEMA_COMPARTIDO = re.compile(
    r"(usuario|credencial(?:es)?)\s+compartid[oa]s?\s+(?:de|del|para)\s+[\wÁÉÍÓÚñÑ\s]{2,30}",
    re.IGNORECASE,
)


class PiiService:

    @staticmethod
    def sanitizar(texto: str) -> tuple[str, int]:
        if not texto:
            return texto, 0

        reemplazos = 0
        resultado = texto

        def _mock(m):
            nonlocal reemplazos
            reemplazos += 1
            return "[MOCK_DATA]"

        def _sistema(m):
            nonlocal reemplazos
            reemplazos += 1
            return "[SISTEMA_COMPARTIDO]"

        resultado = _PATRON_SISTEMA_COMPARTIDO.sub(_sistema, resultado)
        for patron in _PATRONES_MOCK:
            resultado = patron.sub(_mock, resultado)

        return resultado, reemplazos
