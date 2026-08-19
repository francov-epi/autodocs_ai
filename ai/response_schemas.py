"""
response_schemas.py — define, por Gem, la forma EXACTA de JSON que Gemini
debe devolver (generationConfig.responseSchema).

Por qué existe este archivo: pedirle a un modelo "respondé solo en JSON"
(responseMimeType=application/json) garantiza sintaxis JSON válida, pero NO
garantiza que use los nombres de campo que el resto de la aplicación espera
— un modelo puede perfectamente devolver JSON válido con su propia
estructura inventada (fue justo lo que pasó con la Gem SDD: en vez de
"archivos_flujo" devolvió "seccion_8.archivos"). responseSchema cierra ese
margen: restringe la generación a los nombres de campo y tipos declarados
acá, así que si algún día un Gem "inventa" una sección nueva, hay que
agregarla primero en este archivo (y en el service que la parsea) antes de
que el modelo pueda usarla.

Formato: subconjunto de OpenAPI Schema Object que acepta la API de Gemini
(type/properties/items/required, tipos en minúscula: object/array/string/
number/integer/boolean). No soporta additionalProperties ni validaciones
más finas (regex, min/max) — mantenerlo simple.
"""

_STR = {"type": "string"}
_STR_ARR = {"type": "array", "items": _STR}


def _obj(props: dict, required: list = None) -> dict:
    schema = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


PDD_SCHEMA = _obj({
    "nombre_proceso": _STR, "area_proceso": _STR, "area": _STR, "descripcion_breve": _STR,
    "objetivos": _STR, "roles_aplicaciones": _STR, "horario_frecuencia": _STR,
    "veces_ejecucion": _STR, "tiempo_ejecucion": _STR, "restricciones": _STR,
    "periodo_pico": _STR, "volumen_pico": _STR, "personas_proceso": _STR,
    "datos_entrada": _STR, "datos_salida": _STR,
    "aplicaciones": {"type": "array", "items": _obj({
        "nombre": _STR, "version": _STR, "idioma": _STR, "acceso": _STR, "comentario": _STR})},
    "camino_feliz": {"type": "array", "items": _obj({
        "numero": _STR, "descripcion": _STR, "resultado_esperado": _STR,
        "regla_negocio": _STR, "comentarios": _STR})},
    "dentro_alcance": _STR_ARR,
    "fuera_alcance": {"type": "array", "items": _obj({"actividad": _STR, "motivo": _STR})},
    "excepciones_negocio_conocidas": {"type": "array", "items": _obj({
        "nombre": _STR, "accion": _STR, "parametros": _STR, "accion_a_realizar": _STR})},
    "excepciones_negocio_desconocidas": _STR,
    "errores_sistema_conocidos": {"type": "array", "items": _obj({
        "nombre": _STR, "accion": _STR, "parametros": _STR, "accion_a_ejecutar": _STR})},
    "errores_sistema_desconocidos": _STR,
    "reportes": {"type": "array", "items": _obj({"tipo": _STR, "frecuencia": _STR, "detalle": _STR})},
    "supuestos": _STR_ARR, "preguntas_abiertas": _STR_ARR,
}, required=["nombre_proceso", "camino_feliz"])

SDD_SCHEMA = _obj({
    "nombre_robot": _STR,
    "revision": _obj({"fecha": _STR, "version": _STR, "descripcion": _STR,
                       "autor": _STR, "revisor": _STR, "aprobador": _STR, "cargo": _STR}),
    "introduccion": _STR, "objetivos": _STR,
    "contacto_analista": _STR, "contacto_analista_mail": _STR,
    "contacto_dev": _STR, "contacto_dev_mail": _STR,
    "contacto_cliente": _STR, "contacto_cliente_mail": _STR,
    "tipo_robot": _STR, "usa_orquestador": _STR, "escalable": _STR, "version_plataforma": _STR,
    "ambiente_produccion": _STR, "prerequisitos_ejecutar": _STR, "datos_entrada": _STR,
    "datos_salida": _STR, "como_empezar": _STR, "reportes": _STR, "uso_orquestador": _STR,
    "politica_contrasenas": _STR, "credenciales_guardadas": _STR, "lista_queues": _STR,
    "detalles_calendario": _STR, "multiples_resoluciones": _STR, "resolucion_recomendada": _STR,
    "ambiente_desarrollo": _STR, "prerequisito_ambiente": _STR, "repositorios": _STR,
    "metodo_configuracion": _STR, "componentes_reutilizados": _STR, "nuevos_componentes": _STR,
    "packages": {"type": "array", "items": _obj({"nombre": _STR, "descripcion": _STR})},
    "archivos_flujo": {"type": "array", "items": _obj({
        "archivo": _STR, "descripcion": _STR, "argumentos": _STR})},
    "seguimiento_ejecuciones": _STR, "tips_soporte": _STR, "mejoras_futuras": _STR_ARR,
    "recursos_externos": {"type": "array", "items": _obj({
        "recurso": _STR, "web": _STR, "descripcion": _STR})},
    "glosario": {"type": "array", "items": _obj({"termino": _STR, "descripcion": _STR})},
    "supuestos": _STR_ARR, "preguntas_abiertas": _STR_ARR,
}, required=["nombre_robot", "archivos_flujo"])

ESTIMACION_SCHEMA = _obj({
    "proceso": _STR,
    "fases": {"type": "array", "items": _obj({
        "fase": _STR, "task": _STR, "entregable": _STR, "responsable": _STR,
        "horas": {"type": "number"}})},
    "detalle_desarrollo": {"type": "array", "items": _obj({
        "observacion": _STR, "tarea": _STR, "complejidad": _STR,
        "sistemas_externos": _STR, "horas": {"type": "number"}, "reutilizando": {"type": "number"}})},
    "otras_consideraciones": _STR, "supuestos": _STR_ARR, "preguntas_abiertas": _STR_ARR,
}, required=["fases"])

SUPERVISOR_SCHEMA = _obj({
    "consistente": {"type": "boolean"},
    "alertas": _STR_ARR,
}, required=["consistente", "alertas"])

QA_SCHEMA = _obj({
    "modulo_general": _STR,
    "casos": {"type": "array", "items": _obj({
        "modulo": _STR,
        "funcionalidad": _STR,
        "nombre_caso": _STR,
        "precondiciones": _STR,
        "instrucciones_ejecucion": _STR,
        "resultado_esperado": _STR,
        "criticidad": _STR,
        "tipo": _STR,
    }, required=["nombre_caso", "instrucciones_ejecucion", "resultado_esperado"])},
}, required=["casos"])

POR_GEM = {
    "pdd": PDD_SCHEMA,
    "sdd": SDD_SCHEMA,
    "estimacion": ESTIMACION_SCHEMA,
    "supervisor": SUPERVISOR_SCHEMA,
    "qa": QA_SCHEMA,
}
