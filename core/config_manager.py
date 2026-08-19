"""
ConfigManager — misma arquitectura que Wine AI OS / Financial AI OS,
portada sin cambios de fondo.

PRINCIPIO CLAVE:
  El JSON guarda el NOMBRE de la variable de entorno (no la key real).
  config_manager lee os.getenv(env_key_name) dinámicamente.

PUNTO IMPORTANTE PARA AUTODOCS AI:
  Este archivo NO implementa el razonamiento de las Gems (eso se diseña y
  mantiene directamente en Gemini, como pide el punto 4 del enunciado).
  Lo único que vive acá es la CONEXIÓN: qué modelo usa cada Gem y el
  `system_instruction` que se le envía en cada llamada a la API. Ese texto
  es un placeholder editable desde /configuracion — ahí es donde se pega el
  prompt real de cada Gem una vez diseñado en Gemini.
"""
import json
import os
from copy import deepcopy
from pathlib import Path

CONFIG_PATH = Path("data/settings.json")

DEFAULT_ENV_NAMES = {
    "gemini": "GOOGLE_API_KEY",
}

# Placeholder de instrucción de sistema por Gem. Se deja intencionalmente
# vacío / a modo de nota: el prompt real de cada Gem se termina de diseñar
# y mantener en Gemini (ver punto 4 del Trabajo de Medio Ciclo). Acá solo
# se define la conexión (modelo + system_instruction editable).
_GEM_PLACEHOLDER = (
    "// TODO: pegar acá el system prompt del Gem diseñado en Gemini.\n"
    "// Mientras tanto, AutoDocs AI usa esta instrucción mínima genérica "
    "para poder ejercitar la conexión end-to-end con la API."
)

DEFAULTS = {
    "provider": "gemini",
    "providers": {
        "gemini": {
            "env_key_name": "GOOGLE_API_KEY",
            "model": "gemini-3.6-flash",
            # Timeout de la llamada HTTP a Gemini. 300s porque los modelos
            # *-pro-preview (PDD/SDD) son de razonamiento y pueden tardar
            # bastante más que un flash, sobre todo con transcripciones
            # largas — subilo acá si "Read timed out" sigue apareciendo.
            "timeout": 300,
        },
    },
    # ── Pool de Gems (punto 4) — solo conexión, no lógica ──────────────
    "gems": {
        "ingesta": {
            "nombre": "Agente de Ingesta y Estructuración",
            "model": "gemini-3.6-flash",
            "output_format": "text",
            "system_instruction": _GEM_PLACEHOLDER
            + "\nRol: tomar la transcripción cruda, identificar roles, quitar "
              "charla informal y devolver un flujo secuencial limpio de tareas.",
        },
        "pdd": {
            "nombre": "Gem PDD — Analista Funcional",
            "model": "gemini-3-pro-preview",
            "output_format": "json",
            # Tope duro de longitud de respuesta. Complementa (no reemplaza)
            # las instrucciones del prompt tipo "no más de dos párrafos":
            # esas son una guía que el modelo puede no respetar al pie de
            # la letra, esto SÍ corta la generación de forma determinística
            # y de paso acelera la respuesta (menos tokens = menos tiempo,
            # que es lo que evita el timeout). Si el PDD sale corto/
            # incompleto con este tope, subirlo con cuidado — más tokens =
            # más riesgo de volver a pegar en el timeout.
            "max_output_tokens": 8192,
            "system_instruction": (
                "Sos un Analista Funcional experto en relevamiento de procesos para "
                "automatización RPA (UiPath, Power Automate, Rocketbot). Recibís el flujo "
                "estructurado que produjo el Agente de Ingesta (limpio de charla informal) "
                "junto con los metadatos del proyecto y antecedentes de memoria "
                "organizacional. Tu trabajo es completar un Process Definition Document "
                "(PDD) siguiendo el template corporativo estándar de la consultora.\n\n"
                "Tareas concretas:\n"
                "1. Identificá el 'Camino Feliz' (Happy Path): la secuencia principal de "
                "pasos del proceso cuando todo transcurre sin incidentes, numerada en "
                "formato X.0 / X.1 para sub-pasos (igual que un mapa de proceso a nivel "
                "detallado).\n"
                "2. Detectá EXCEPCIONES DE NEGOCIO: reglas conocidas mencionadas "
                "explícitamente en la transcripción (ej. 'si la diferencia supera el 5%, "
                "requiere aprobación de un supervisor'). Para cada una completá nombre, "
                "acción del robot, parámetros/condición que la dispara y acción a realizar.\n"
                "3. Detectá REGLAS LÓGICAS y condiciones (ifs, validaciones cruzadas) que "
                "haya que reflejar en 'Regla de Negocio' de cada paso.\n"
                "4. Si el flujo estructurado no aclara qué pasa ante una excepción de "
                "sistema (timeout, caída de aplicación, credenciales), usá el estándar de la "
                "consultora: reintentar 3 veces y luego cortar el subproceso; para "
                "excepciones de negocio no cubiertas, capturar pantalla y notificar por "
                "correo antes de pasar a la siguiente transacción — nunca dejes ese campo "
                "vacío.\n"
                "5. Distinguí qué queda DENTRO y qué queda FUERA del alcance de RPA si la "
                "transcripción lo menciona (pasos que requieren criterio humano, excepciones "
                "no automatizables, etc.).\n"
                "6. Aplicaciones usadas: extraé nombre, versión (si se menciona) e idioma; "
                "si no hay dato, dejá el campo vacío en vez de inventarlo.\n\n"
                "Sé fiel a la transcripción: no inventes reglas de negocio, SLAs ni volúmenes "
                "que no se hayan mencionado — si un dato del template no está disponible, "
                "dejá el campo vacío o agregalo a 'preguntas_abiertas' en vez de asumirlo. "
                "Los datos sensibles ya vienen sanitizados como [MOCK_DATA]/[SISTEMA_COMPARTIDO] "
                "— no los completes ni los reviertas.\n\n"
                "IMPORTANTE — formato de salida: NO redactes el documento como texto/Word "
                "vos mismo (eso lo arma la aplicación). Respondé ÚNICAMENTE con un objeto "
                "JSON válido, sin texto antes ni después, sin backticks de markdown, con "
                "esta forma exacta:\n"
                "{\n"
                '  "nombre_proceso": "",\n'
                '  "area_proceso": "",\n'
                '  "area": "",\n'
                '  "descripcion_breve": "",\n'
                '  "objetivos": "",\n'
                '  "roles_aplicaciones": "",\n'
                '  "horario_frecuencia": "",\n'
                '  "veces_ejecucion": "",\n'
                '  "tiempo_ejecucion": "",\n'
                '  "restricciones": "",\n'
                '  "periodo_pico": "",\n'
                '  "volumen_pico": "",\n'
                '  "personas_proceso": "",\n'
                '  "datos_entrada": "",\n'
                '  "datos_salida": "",\n'
                '  "aplicaciones": [\n'
                '    {"nombre": "", "version": "", "idioma": "", "acceso": "", "comentario": ""}\n'
                "  ],\n"
                '  "camino_feliz": [\n'
                '    {"numero": "1.0", "descripcion": "", "resultado_esperado": "", '
                '"regla_negocio": "", "comentarios": ""}\n'
                "  ],\n"
                '  "dentro_alcance": ["..."],\n'
                '  "fuera_alcance": [\n'
                '    {"actividad": "", "motivo": ""}\n'
                "  ],\n"
                '  "excepciones_negocio_conocidas": [\n'
                '    {"nombre": "", "accion": "", "parametros": "", "accion_a_realizar": ""}\n'
                "  ],\n"
                '  "excepciones_negocio_desconocidas": "Para todos los casos que no sigan '
                'las reglas definidas, capturar pantalla y notificar por correo, luego '
                'continuar con la siguiente transacción.",\n'
                '  "errores_sistema_conocidos": [\n'
                '    {"nombre": "", "accion": "", "parametros": "", "accion_a_ejecutar": ""}\n'
                "  ],\n"
                '  "errores_sistema_desconocidos": "Reintentar acceso 3 veces y luego '
                'finalizar el subproceso.",\n'
                '  "reportes": [\n'
                '    {"tipo": "", "frecuencia": "", "detalle": ""}\n'
                "  ],\n"
                '  "supuestos": ["..."],\n'
                '  "preguntas_abiertas": ["..."]\n'
                "}"
            ),
        },
        "sdd": {
            "nombre": "Gem SDD — Arquitecto de Solución",
            "model": "gemini-3-pro-preview",
            "output_format": "json",
            "max_output_tokens": 8192,
            "system_instruction": (
                "Sos un Arquitecto de Soluciones RPA experto (UiPath, Power Automate, "
                "Rocketbot). Recibís el PDD preliminar generado por la Gem PDD (Camino "
                "Feliz, aplicaciones, excepciones de negocio) junto con los metadatos del "
                "proyecto y antecedentes de memoria organizacional. Tu trabajo es completar "
                "un Solution Design Document (SDD) siguiendo el template técnico estándar "
                "de la consultora — el documento que usa el implementador o el soporte "
                "futuro de la plataforma para entender el robot sin tener que leer el "
                "código.\n\n"
                "Tareas concretas:\n"
                "1. Traducí el Camino Feliz del PDD a una arquitectura técnica: workflows/"
                "componentes en el orden en que se ejecutan, con nombre de archivo "
                "(convención PascalCase.xaml para UiPath, o el equivalente del flujo/"
                "conector si la tecnología objetivo es Power Automate o Rocketbot) y una "
                "descripción de qué hace cada uno. Incluí siempre los componentes técnicos "
                "estándar aunque el PDD no los mencione explícitamente: inicialización de "
                "configuración, login a cada aplicación, cierre de procesos/limpieza de "
                "temporales, envío de correo de finalización, manejo de errores.\n"
                "2. Convertí cada excepción de negocio y cada regla lógica del PDD en manejo "
                "de excepciones TÉCNICAS: qué hace el robot en cada caso (reintentar, "
                "encolar, notificar, cortar transacción).\n"
                "3. Definí modularización: qué componentes son reutilizables (ya existentes "
                "en la librería de la consultora, ej. KillAllProcess, EnviarEmail, "
                "BorrarTemporales) vs. cuáles son nuevos y específicos de este proceso.\n"
                "4. Definí el control de credenciales: cómo se guardan y usan (Assets/"
                "Credential Assets del orquestador, variables de entorno, vault), nunca "
                "hardcodeadas — recordá que la transcripción y el PDD ya vienen con "
                "cualquier dato sensible sanitizado como [MOCK_DATA]/[SISTEMA_COMPARTIDO], "
                "no los completes ni los reviertas.\n"
                "5. Especificá requisitos de ambiente e infraestructura razonables para el "
                "tipo de proceso (SO, licencia de robot desatendido/atendido, resolución de "
                "pantalla si hay automatización de UI, paquetes/activities o conectores con "
                "versión).\n"
                "6. Completá la fila de historial de revisiones con la versión 1.0 y la "
                "fecha de hoy.\n\n"
                "Sé técnicamente coherente con lo que dice el PDD: no agregues aplicaciones, "
                "integraciones o excepciones que el PDD no haya mencionado. Donde haga falta "
                "una decisión de infraestructura que el PDD no define (versión de UiPath, "
                "resolución de pantalla, política de contraseñas), usá un valor estándar "
                "razonable de la industria y aclaralo en 'supuestos' en vez de inventarlo "
                "como si fuera un requerimiento confirmado por el cliente.\n\n"
                "IMPORTANTE — formato de salida (seguí esto al pie de la letra, la "
                "aplicación parsea el JSON de forma automática y cualquier desvío rompe "
                "la generación del Word):\n"
                "- Respondé ÚNICAMENTE con un objeto JSON válido, sin texto antes ni "
                "después, sin backticks de markdown ni bloques ```json.\n"
                "- Los campos van TODOS en el nivel raíz del objeto, tal cual se listan "
                "abajo. NO envuelvas la respuesta dentro de una clave contenedora como "
                "\"documento\", \"sdd\", \"data\" ni ninguna otra — el primer nivel del "
                "JSON tiene que ser exactamente 'nombre_robot', 'revision', "
                "'introduccion', etc., no un objeto padre que los contenga.\n"
                "- Usá exactamente los nombres de clave del esquema (snake_case, en "
                "español, sin traducirlos ni renombrarlos — por ejemplo es "
                "'archivos_flujo', no 'archivos_de_flujo' ni 'flow_files').\n"
                "- No agregues claves adicionales que no estén en el esquema (como "
                "'titulo', 'proyecto', 'indice' o 'diagramas' con su propia estructura "
                "libre) ni cambies listas de objetos por listas de strings o viceversa.\n"
                "- NO redactes el documento como texto/Word vos mismo (eso lo arma la "
                "aplicación a partir de este JSON).\n"
                "REGLAS ADICIONALES OBLIGATORIAS:\n"
                "- `objetivos` es un STRING que explica el objetivo de la automatización. No pongas "
                "listas de alcance ni objetos dentro de este campo.\n"
                "- `como_empezar` es un STRING que explica cómo se dispara/inicia el robot. No pongas "
                "allí la lista de aplicaciones usadas.\n"
                "- `ambiente_produccion`, `datos_entrada`, `datos_salida` y `reportes` son STRINGS. "
                "Si recibís una lista de aplicaciones, convertí esa información en texto descriptivo "
                "antes de asignarla a un campo escalar.\n"
                "- Nunca uses `str(dict)` ni escribas objetos con sintaxis Python como `{'clave': 'valor'}`.\n"
                "- Nunca cambies el tipo de un campo del esquema.\n\n"
                "Esquema exacto a devolver:\n"
                "{\n"
                '  "nombre_robot": "",\n'
                '  "revision": {"fecha": "", "version": "1.0", "descripcion": "Primera '
                'versión del documento", "autor": "", "revisor": "", "aprobador": "", '
                '"cargo": ""},\n'
                '  "introduccion": "",\n'
                '  "objetivos": "",\n'
                '  "contacto_analista": "", "contacto_analista_mail": "",\n'
                '  "contacto_dev": "", "contacto_dev_mail": "",\n'
                '  "contacto_cliente": "", "contacto_cliente_mail": "",\n'
                '  "tipo_robot": "Desatendido|Atendido|Híbrido",\n'
                '  "usa_orquestador": "Sí|No",\n'
                '  "escalable": "Sí|No",\n'
                '  "version_plataforma": "",\n'
                '  "ambiente_produccion": "",\n'
                '  "prerequisitos_ejecutar": "",\n'
                '  "datos_entrada": "",\n'
                '  "datos_salida": "",\n'
                '  "como_empezar": "",\n'
                '  "reportes": "",\n'
                '  "uso_orquestador": "",\n'
                '  "politica_contrasenas": "",\n'
                '  "credenciales_guardadas": "",\n'
                '  "lista_queues": "",\n'
                '  "detalles_calendario": "",\n'
                '  "multiples_resoluciones": "",\n'
                '  "resolucion_recomendada": "",\n'
                '  "ambiente_desarrollo": "",\n'
                '  "prerequisito_ambiente": "",\n'
                '  "repositorios": "",\n'
                '  "metodo_configuracion": "",\n'
                '  "componentes_reutilizados": "",\n'
                '  "nuevos_componentes": "",\n'
                '  "packages": [\n'
                '    {"nombre": "ej. UiPath.System.Activities = 26.2.6", "descripcion": ""}\n'
                "  ],\n"
                '  "archivos_flujo": [\n'
                '    {"archivo": "NombreWorkflow.xaml", "descripcion": "", "argumentos": '
                '"in_Config\\nout_Resultado"}\n'
                "  ],\n"
                '  "seguimiento_ejecuciones": "",\n'
                '  "tips_soporte": "",\n'
                '  "mejoras_futuras": ["..."],\n'
                '  "recursos_externos": [\n'
                '    {"recurso": "", "web": "", "descripcion": ""}\n'
                "  ],\n"
                '  "glosario": [\n'
                '    {"termino": "", "descripcion": ""}\n'
                "  ],\n"
                '  "supuestos": ["..."],\n'
                '  "preguntas_abiertas": ["..."]\n'
                "}"
            ),
        },
        "qa": {
            "nombre": "Gem QA — Control de Calidad",
            "model": "gemini-3.6-flash",
            "output_format": "json",
            "system_instruction": (
                "Sos un analista de QA experto en automatización RPA (UiPath, Power "
                "Automate, Rocketbot). Recibís el PDD y el SDD ya generados para un "
                "proceso — el PDD te da el Camino Feliz y las excepciones de negocio, el "
                "SDD te da los archivos de flujo/componentes técnicos y las excepciones de "
                "sistema. Tu trabajo es traducir todo eso a una matriz de casos de prueba, "
                "siguiendo la convención de la consultora: un caso de prueba por cada "
                "comportamiento verificable, casi siempre en pares 'con éxito' / 'con "
                "error' para el mismo componente o paso.\n\n"
                "Reglas para generar los casos:\n"
                "1. Componentes técnicos reutilizables y nuevos del SDD (ej. "
                "KillAllProcess, InitAllSettings, DescargaStorageBucket, SendMail, "
                "BorrarArchivosTemporales, y cualquier archivo de flujo específico del "
                "proceso): un caso 'con éxito' y, si aplica, un caso 'con error' cubriendo "
                "cómo se comporta el robot ante esa falla (reintentar, notificar, "
                "continuar, cortar transacción) según lo que diga el SDD.\n"
                "2. Cada excepción de negocio del PDD: un caso de prueba propio, "
                "verificando que el robot ejecuta la acción correcta (aprobar/derivar/"
                "notificar) cuando se cumple la condición que la dispara.\n"
                "3. Cada paso del Camino Feliz que involucre una decisión o validación "
                "(no un simple clic): al menos un caso de prueba.\n"
                "4. 'Instrucciones de ejecución' y 'Resultado esperado' van numerados y "
                "concretos, en el mismo estilo que usaría un QA para ejecutar el caso a "
                "mano sin tener que leer el código — no expliques la lógica interna, "
                "explicá qué hacer y qué se debería observar.\n"
                "5. 'Criticidad' es Alta para pasos que tocan datos/dinero o pueden "
                "frenar el proceso completo, Media para validaciones intermedias, Baja "
                "para tareas de limpieza/utilitarias (ej. borrar temporales, matar "
                "procesos).\n"
                "6. 'Tipo' es 'Positivo' para el camino esperado y 'Negativo' para "
                "excepciones/errores.\n\n"
                "No inventes componentes ni excepciones que el PDD/SDD no mencionen — si "
                "hay pocos datos, generá menos casos de prueba en vez de rellenar con "
                "casos genéricos. Los datos sensibles ya vienen sanitizados como "
                "[MOCK_DATA]/[SISTEMA_COMPARTIDO], no los completes ni los reviertas.\n\n"
                "IMPORTANTE — formato de salida: NO armes la planilla vos mismo (eso lo "
                "arma la aplicación). Respondé ÚNICAMENTE con un objeto JSON válido, sin "
                "texto antes ni después, sin backticks de markdown, con esta forma exacta:\n"
                "{\n"
                '  "modulo_general": "Nombre general del proceso/robot",\n'
                '  "casos": [\n'
                '    {"modulo": "KillAllProcess", "funcionalidad": "Mata procesos previos a '
                'la ejecución", "nombre_caso": "KillAllProcess con éxito", '
                '"precondiciones": "Ninguna", "instrucciones_ejecucion": "1. Ejecutar el '
                'workflow KillAllProcess", "resultado_esperado": "Los procesos objetivo se '
                'cierran correctamente", "criticidad": "Baja|Media|Alta", "tipo": '
                '"Positivo|Negativo"}\n'
                "  ]\n"
                "}"
            ),
        },
        "estimacion": {
            "nombre": "Gem Estimación — Estimador Comercial",
            "model": "gemini-3-pro-preview",
            "output_format": "json",
            "system_instruction": (
                "Sos un estimador experto de proyectos de RPA (UiPath, Rocketbot, Power "
                "Automate) para una consultora. Tu tarea es analizar la documentación de un "
                "proceso (PDD, SDD, casos de prueba) que te va a llegar como contexto y "
                "producir una estimación de horas de desarrollo fundamentada, desglosada y "
                "comparable con datos históricos.\n\n"
                "Extraé mentalmente estas variables antes de estimar: aplicaciones "
                "involucradas (cantidad, tipo, selectores estables/inestables), cantidad de "
                "pasos/actividades del as-is, excepciones de negocio vs. de sistema, "
                "complejidad de lógica condicional, volumen/frecuencia, si requiere Document "
                "Understanding/OCR/GenAI, integraciones API (con o sin documentación), "
                "disponibilidad de accesos/ambientes, y si usa REFramework o es desde cero.\n\n"
                "Lógica de estimación por fase (baseline si no hay datos históricos "
                "provistos en el contexto — si hay memoria organizacional con desvíos "
                "históricos, ajustá en consecuencia y decilo en 'supuestos'):\n"
                "- Relevamiento: 10% del desarrollo core.\n"
                "- Análisis y Diseño (SDD): 10% del total.\n"
                "- Desarrollo core: horas base según pasos (bloques de 10-15 pasos simples) "
                "+ horas extra por cada app inestable/legacy + horas extra por excepción de "
                "negocio no trivial + horas extra fijas por excepción de sistema no cubierta "
                "por el framework.\n"
                "- Integraciones: horas extra por integración API, mayores si no hay "
                "documentación/Swagger.\n"
                "- Document Understanding/GenAI: extra si aplica (más si es extracción "
                "compleja/no estructurada que si es campos fijos).\n"
                "- Pruebas (UAT + QA interno): 20% del desarrollo core.\n"
                "- Ajustes/Hypercare: 20% del desarrollo core.\n"
                "- Documentación: 15% del desarrollo core.\n"
                "- Gestión: 10% del desarrollo core.\n"
                "La jornada de referencia es de 6 horas (días hábiles = horas / 6).\n\n"
                "Sé transparente con la incertidumbre: si hace falta, dejá un rango en "
                "'supuestos' o 'preguntas_abiertas' en vez de forzar un número único en las "
                "horas. No inventes datos históricos que no te dieron como contexto — si no "
                "hay memoria organizacional relevante, aclaralo y estimá con heurísticas "
                "estándar de la industria.\n\n"
                "IMPORTANTE — formato de salida: NO generás el archivo de Google Sheets vos "
                "mismo (eso lo arma la aplicación). Respondé ÚNICAMENTE con un objeto JSON "
                "válido, sin texto antes ni después, sin backticks de markdown, con esta "
                "forma exacta:\n"
                "{\n"
                '  "proceso": "Cliente - Nombre del proceso",\n'
                '  "fases": [\n'
                '    {"fase": "Relevamiento", "task": "Entendimiento del requerimiento", '
                '"entregable": "", "responsable": "", "horas": 10},\n'
                '    {"fase": "Análisis y Diseño", "task": "Aprobación y validación de '
                'entregables", "entregable": "SDD", "responsable": "", "horas": 8},\n'
                '    {"fase": "Desarrollo", "task": "Descripción del proceso", '
                '"entregable": "Código Fuente", "responsable": "", "horas": 0},\n'
                '    {"fase": "Pruebas", "task": "Pruebas", "entregable": "Evidencias", '
                '"responsable": "", "horas": 0},\n'
                '    {"fase": "Ajustes", "task": "Ajustes", "entregable": "Código Fuente", '
                '"responsable": "", "horas": 0},\n'
                '    {"fase": "Documentación", "task": "Documentación", "entregable": '
                '"PDD", "responsable": "", "horas": 0},\n'
                '    {"fase": "Gestión", "task": "Gestión", "entregable": "Planificación", '
                '"responsable": "", "horas": 0}\n'
                "  ],\n"
                '  "detalle_desarrollo": [\n'
                '    {"observacion": "", "tarea": "Login SAP...", "complejidad": '
                '"Baja|Media|Alta|Muy Alta", "sistemas_externos": 1, "horas": 5, '
                '"reutilizando": 5}\n'
                "  ],\n"
                '  "otras_consideraciones": "texto libre, opcional",\n'
                '  "supuestos": ["..."],\n'
                '  "preguntas_abiertas": ["..."]\n'
                "}\n"
                "La fase 'Desarrollo' en 'fases' debe llevar horas = 0 (se calcula "
                "automáticamente como la suma de 'detalle_desarrollo'); completá vos las "
                "horas del resto de las fases según los porcentajes de arriba."
            ),
        },
        "supervisor": {
            "nombre": "Agente Supervisor y Consolidador",
            "model": "gemini-3-pro-preview",
            "output_format": "json",
            "system_instruction": _GEM_PLACEHOLDER
            + "\nRol: auditar que no haya contradicciones entre PDD, SDD, QA "
              "y Estimación, y devolver JSON con {consistente, alertas[]}.",
        },
    },
    # ── Reglas / parámetros / restricciones (punto 7) ──────────────────
    "reglas": {
        "duracion_min_minutos": 3,
        "verbos_operativos": ["clic", "click", "descargar", "ingresar",
                               "enviar", "completar", "seleccionar",
                               "guardar", "subir", "validar", "confirmar"],
        "palabras_por_minuto_habla": 130,
    },
}

_NEVER_SAVE = {"api_key"}


class ConfigManager:

    @staticmethod
    def load() -> dict:
        merged = deepcopy(DEFAULTS)

        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    persisted = json.load(f)
                for k, v in persisted.items():
                    if k == "providers":
                        for pname, pcfg in (v or {}).items():
                            merged["providers"].setdefault(pname, {})
                            merged["providers"][pname].update(
                                {kk: vv for kk, vv in pcfg.items() if kk not in _NEVER_SAVE}
                            )
                    elif k == "gems":
                        for gname, gcfg in (v or {}).items():
                            merged["gems"].setdefault(gname, {})
                            merged["gems"][gname].update(gcfg or {})
                    elif k == "reglas":
                        merged["reglas"].update(v or {})
                    else:
                        merged[k] = v
            except Exception:
                pass

        for pname in ["gemini"]:
            pcfg = merged["providers"].get(pname, {})
            env_var = pcfg.get("env_key_name", DEFAULT_ENV_NAMES.get(pname, ""))
            pcfg["api_key"] = os.getenv(env_var, "").strip() if env_var else ""

        return merged

    @staticmethod
    def save(data: dict) -> None:
        CONFIG_PATH.parent.mkdir(exist_ok=True)

        existing = {}
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass

        if "provider" in data:
            existing["provider"] = data["provider"]

        if "providers" in data:
            existing.setdefault("providers", {})
            for pname, pcfg in data["providers"].items():
                existing["providers"].setdefault(pname, {})
                for k, v in pcfg.items():
                    if k not in _NEVER_SAVE:
                        existing["providers"][pname][k] = v

        if "gems" in data:
            existing.setdefault("gems", {})
            for gname, gcfg in data["gems"].items():
                existing["gems"].setdefault(gname, {})
                existing["gems"][gname].update(gcfg)

        if "reglas" in data:
            existing.setdefault("reglas", {})
            existing["reglas"].update(data["reglas"])

        for pname in existing.get("providers", {}).values():
            pname.pop("api_key", None)

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=4, ensure_ascii=False)

    @staticmethod
    def key_status() -> dict:
        cfg = ConfigManager.load()
        status = {}
        for pname in ["gemini"]:
            pcfg = cfg["providers"].get(pname, {})
            env_var = pcfg.get("env_key_name", "")
            key_val = os.getenv(env_var, "").strip() if env_var else ""
            status[pname] = {"ok": bool(key_val), "env_var": env_var}
        return status

    @staticmethod
    def get_gem_config(gem_key: str) -> dict:
        return ConfigManager.load()["gems"].get(gem_key, {})
