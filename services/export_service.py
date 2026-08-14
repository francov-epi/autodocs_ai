"""
ExportService — genera los artefactos finales en los formatos que el
enunciado indica en su stack tecnológico de referencia: PDD/SDD en Word
(python-docx) y la planilla de Estimación en Excel (openpyxl). QA se exporta
también como Excel por tratarse de una matriz tabular.

Este módulo NO decide el contenido (eso es responsabilidad de las Gems):
solo vuelca el texto ya generado sobre un layout con la identidad visual
mínima de un template corporativo (encabezado, título, cuerpo).
"""
import io
from datetime import datetime

from docx import Document
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


def _docx_desde_texto(titulo: str, subtitulo: str, cuerpo: str) -> io.BytesIO:
    doc = Document()

    h = doc.add_heading(titulo, level=0)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x1A, 0x2A, 0x5C)

    p = doc.add_paragraph(subtitulo)
    p.runs[0].italic = True
    p.runs[0].font.size = Pt(10)

    doc.add_paragraph(f"Generado por AutoDocs AI — {datetime.now():%d/%m/%Y %H:%M}")
    doc.add_paragraph("")

    for bloque in (cuerpo or "").split("\n"):
        linea = bloque.strip()
        if not linea:
            doc.add_paragraph("")
        elif linea.startswith("### "):
            doc.add_heading(linea[4:], level=3)
        elif linea.startswith("## "):
            doc.add_heading(linea[3:], level=2)
        elif linea.startswith("# "):
            doc.add_heading(linea[2:], level=1)
        elif linea.startswith(("- ", "* ")):
            doc.add_paragraph(linea[2:], style="List Bullet")
        else:
            doc.add_paragraph(linea)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def _xlsx_desde_texto(titulo: str, cuerpo: str) -> io.BytesIO:
    """Vuelca el texto de la Gem en una planilla simple: si detecta líneas
    separadas por ' | ' las interpreta como filas tabulares; el resto va
    como texto libre en la primera columna."""
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]

    header_fill = PatternFill(start_color="1A2A5C", end_color="1A2A5C", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    fila = 1
    ws.cell(row=fila, column=1, value=titulo).font = Font(bold=True, size=14)
    fila += 2

    for linea in (cuerpo or "").split("\n"):
        linea = linea.strip()
        if not linea:
            continue
        if "|" in linea:
            celdas = [c.strip(" -") for c in linea.split("|") if c.strip(" -")]
            if not celdas:
                continue
            for col, valor in enumerate(celdas, start=1):
                cell = ws.cell(row=fila, column=col, value=valor)
                if fila == 3 or linea.lower().startswith(("condición", "campo", "excepción")):
                    cell.fill = header_fill
                    cell.font = header_font
        else:
            ws.cell(row=fila, column=1, value=linea.lstrip("-* "))
        fila += 1

    for col in range(1, 8):
        ws.column_dimensions[get_column_letter(col)].width = 28
    ws.freeze_panes = "A4"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class ExportService:

    @staticmethod
    def pdd_a_docx(proyecto: dict, contenido: str) -> io.BytesIO:
        return _docx_desde_texto(
            f"PDD — {proyecto['proceso']}",
            f"Cliente: {proyecto['cliente']} · Tecnología objetivo: {proyecto.get('tecnologia') or '—'}",
            contenido,
        )

    @staticmethod
    def sdd_a_docx(proyecto: dict, contenido: str) -> io.BytesIO:
        return _docx_desde_texto(
            f"SDD — {proyecto['proceso']}",
            f"Cliente: {proyecto['cliente']} · Criticidad: {proyecto.get('criticidad') or '—'}",
            contenido,
        )

    @staticmethod
    def qa_a_xlsx(proyecto: dict, contenido: str) -> io.BytesIO:
        return _xlsx_desde_texto(f"QA — {proyecto['proceso']}", contenido)

    @staticmethod
    def estimacion_a_xlsx(proyecto: dict, contenido: str) -> io.BytesIO:
        return _xlsx_desde_texto(f"Estimación — {proyecto['proceso']}", contenido)
