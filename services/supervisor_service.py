"""
SupervisorService — interpreta el documento tipo 'SUPERVISOR' guardado por
RelevamientoPipeline._auditar(). A diferencia de PddService/SddService/etc,
el contenido acá NO es la respuesta cruda de una Gem: es el resultado ya
consolidado (JSON propio de la aplicación, ver pipeline/relevamiento_
pipeline.py), así que el parseo es un simple json.loads con un fallback
mínimo por si el documento quedó corrupto.
"""
import json


class SupervisorService:

    @staticmethod
    def parsear(contenido: str) -> dict:
        try:
            data = json.loads(contenido)
            if isinstance(data, dict):
                data.setdefault("consistente", False)
                data.setdefault("alertas", [])
                data.setdefault("documentos_auditados", [])
                data.setdefault("fecha_auditoria", "")
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        return {"consistente": False, "alertas": [], "documentos_auditados": [],
                "fecha_auditoria": "", "error_gem": contenido[:2000]}

    @staticmethod
    def resumen_legible(data: dict) -> str:
        lineas = ["Informe del Agente Supervisor y Consolidador", ""]
        lineas.append(f"Consistente: {'Sí' if data.get('consistente') else 'No'}")
        lineas.append(f"Documentos auditados: {', '.join(data.get('documentos_auditados', [])) or '—'}")
        if data.get("fecha_auditoria"):
            lineas.append(f"Fecha de auditoría: {data['fecha_auditoria']}")
        alertas = data.get("alertas", [])
        lineas.append(f"\nAlertas ({len(alertas)}):")
        if alertas:
            lineas += [f"  · {a}" for a in alertas]
        else:
            lineas.append("  Sin observaciones de consistencia entre PDD, SDD, QA y Estimación.")
        if data.get("error_gem"):
            lineas.append(f"\n⚠ La Gem Supervisor falló durante esta auditoría: {data['error_gem'][:300]}")
        return "\n".join(lineas)
