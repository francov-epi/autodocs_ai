"""
MemoriaService — modelo de memoria en dos niveles (punto 6):

  * Corto plazo: el contexto del proyecto en curso (transcripción,
    flujo estructurado, documentos ya generados) vive directamente en la
    fila de `proyectos` mientras dura el ciclo — cumple el mismo rol que
    Redis en el stack propuesto, sin agregar una dependencia extra a la demo.

  * Largo plazo: `memoria_organizacional`, consultada antes de invocar a
    la Gem Estimación (y disponible para el resto) y actualizada al cierre
    de cada proyecto con el módulo de Aprendizaje Continuo.
"""
from repositories.memoria_repository import MemoriaRepository


class MemoriaService:

    @staticmethod
    def contexto_relevante(texto_proyecto: str) -> str:
        """Arma un bloque de texto con la memoria organizacional relevante
        para inyectar como contexto adicional en las Gems documentales."""
        hallazgos = MemoriaRepository.buscar_relevante(texto_proyecto)
        if not hallazgos:
            return "Sin antecedentes relevantes en la memoria organizacional."
        lineas = [f"- [{h['tipo']}] {h['contenido']}" for h in hallazgos]
        return "Antecedentes de memoria organizacional:\n" + "\n".join(lineas)

    @staticmethod
    def registrar_aprendizaje(proyecto_id: int, tipo: str, tags: list, contenido: str) -> None:
        """Módulo de Aprendizaje Continuo: persiste una corrección o
        desvío observado para que futuros relevamientos lo hereden."""
        MemoriaRepository.agregar(tipo, tags, contenido, proyecto_origen_id=proyecto_id)

    @staticmethod
    def listar() -> list:
        return MemoriaRepository.listar()
