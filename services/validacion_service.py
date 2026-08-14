"""
ValidacionService — Límite Operativo de Entrada (punto 7 del enunciado):
si la transcripción tiene una duración estimada menor al mínimo configurado
o carece de verbos operativos clave, el sistema frena el proceso y pide
contexto adicional, para evitar alucinaciones de las Gems documentales.
"""
from core.config_manager import ConfigManager


class ValidacionService:

    @staticmethod
    def validar_transcripcion(texto: str) -> dict:
        cfg = ConfigManager.load()["reglas"]
        texto_lower = (texto or "").lower()
        palabras = texto.split() if texto else []

        duracion_estimada_min = len(palabras) / max(cfg.get("palabras_por_minuto_habla", 130), 1)
        tiene_verbos = any(v in texto_lower for v in cfg.get("verbos_operativos", []))

        motivos = []
        if duracion_estimada_min < cfg.get("duracion_min_minutos", 3):
            motivos.append(
                f"La transcripción equivale a ~{duracion_estimada_min:.1f} min de habla "
                f"(mínimo configurado: {cfg.get('duracion_min_minutos', 3)} min)."
            )
        if not tiene_verbos:
            motivos.append(
                "No se detectaron verbos operativos clave (clic, descargar, ingresar, "
                "enviar, etc.) que indiquen pasos concretos del proceso."
            )

        return {
            "ok": len(motivos) == 0,
            "duracion_estimada_min": round(duracion_estimada_min, 1),
            "tiene_verbos_operativos": tiene_verbos,
            "motivos": motivos,
        }
