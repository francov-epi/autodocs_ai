"""
SddService — interpreta la respuesta JSON de la Gem SDD (ver
system_instruction en config_manager). Mismo criterio de tolerancia que
PddService/EstimacionService.

Además de la tolerancia a ```json/texto alrededor, este servicio normaliza
desvíos de formato observados en la práctica: el modelo a veces envuelve
la respuesta en una clave contenedora (ej. "documento") con estructura
anidada, y otras veces reparte el contenido en claves hermanas tipo
"seccion_3_contactos", con nombres de sub-campos que también varían de una
generación a otra. _normalizar_wrapper() busca los campos reconocibles en
cualquier parte del árbol JSON (por parecido de nombre, no por ruta fija)
y arma el esquema plano que espera export_service, para no perder la
generación ni degradar a un volcado de JSON crudo en el Word.
"""
import json
import re

_ESQUELETO_VACIO = {
    "nombre_robot": "",
    "revision": {"fecha": "", "version": "1.0", "descripcion": "Primera versión del documento",
                 "autor": "", "revisor": "", "aprobador": "", "cargo": ""},
    "introduccion": "", "objetivos": "",
    "contacto_analista": "", "contacto_analista_mail": "",
    "contacto_dev": "", "contacto_dev_mail": "",
    "contacto_cliente": "", "contacto_cliente_mail": "",
    "tipo_robot": "", "usa_orquestador": "", "escalable": "", "version_plataforma": "",
    "ambiente_produccion": "", "prerequisitos_ejecutar": "", "datos_entrada": "",
    "datos_salida": "", "como_empezar": "", "reportes": "", "uso_orquestador": "",
    "politica_contrasenas": "", "credenciales_guardadas": "", "lista_queues": "",
    "detalles_calendario": "", "multiples_resoluciones": "", "resolucion_recomendada": "",
    "ambiente_desarrollo": "", "prerequisito_ambiente": "", "repositorios": "",
    "metodo_configuracion": "", "componentes_reutilizados": "", "nuevos_componentes": "",
    "packages": [], "archivos_flujo": [],
    "seguimiento_ejecuciones": "", "tips_soporte": "", "mejoras_futuras": [],
    "recursos_externos": [], "glosario": [],
    "supuestos": [], "preguntas_abiertas": [],
}


def _texto(v) -> str:
    """Convierte cualquier valor JSON a texto legible para DOCX.

    Regla crítica: NUNCA usar str(dict), porque produce representación Python
    con llaves y comillas ({'clave': 'valor'}) en el Word.
    """
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, dict):
        # Priorizar campos descriptivos habituales.
        for clave in ("descripcion", "texto", "contenido", "detalle", "accion", "valor"):
            valor = v.get(clave)
            if valor not in (None, "", []):
                texto = _texto(valor)
                if texto:
                    return texto

        # Casos como aplicaciones: {'aplicacion': ..., 'idioma': ...}
        # Se convierten a una línea humana, nunca a str(dict).
        partes = []
        aliases = (
            ("aplicacion", "Aplicación"),
            ("aplicación", "Aplicación"),
            ("nombre", "Nombre"),
            ("version", "Versión"),
            ("idioma", "Idioma"),
            ("environment_access", "Acceso"),
            ("acceso", "Acceso"),
            ("comentario", "Comentario"),
            ("item", "Item"),
            ("titulo", "Título"),
            ("nombre_proceso", "Proceso"),
        )
        usadas = set()
        for clave, etiqueta in aliases:
            if clave in v and v[clave] not in (None, "", []):
                valor = _texto(v[clave])
                if valor:
                    partes.append(f"{etiqueta}: {valor}")
                    usadas.add(clave)

        # Fallback genérico legible para cualquier otra estructura.
        if not partes:
            for clave, valor in v.items():
                if valor in (None, "", []):
                    continue
                texto = _texto(valor)
                if texto:
                    partes.append(f"{str(clave).replace('_', ' ').capitalize()}: {texto}")
        return "\n".join(partes)

    if isinstance(v, list):
        partes = []
        for item in v:
            texto = _texto(item)
            if texto:
                partes.append(texto)
        return "\n".join(partes)

    return str(v)


def _texto_aplicaciones(valor) -> str:
    """Formatea listas de aplicaciones en una representación apta para DOCX."""
    if not isinstance(valor, list):
        return _texto(valor)
    lineas = []
    for app in valor:
        if not isinstance(app, dict):
            texto = _texto(app)
            if texto:
                lineas.append(texto)
            continue
        nombre = app.get("aplicacion") or app.get("aplicación") or app.get("nombre") or "Aplicación"
        detalles = []
        if app.get("version"):
            detalles.append(f"Versión: {_texto(app['version'])}")
        if app.get("idioma"):
            detalles.append(f"Idioma: {_texto(app['idioma'])}")
        acceso = app.get("environment_access") or app.get("acceso")
        if acceso:
            detalles.append(f"Acceso: {_texto(acceso)}")
        if app.get("comentario"):
            detalles.append(f"Comentario: {_texto(app['comentario'])}")
        lineas.append(f"{_texto(nombre)}" + (" — " + "; ".join(detalles) if detalles else ""))
    return "\n".join(lineas)


def _sanear_plano(plano: dict) -> dict:
    """Asegura que los campos escalares jamás lleguen al DOCX como dict/list."""
    escalares = [
        "nombre_robot", "introduccion", "objetivos", "contacto_analista", "contacto_analista_mail",
        "contacto_dev", "contacto_dev_mail", "contacto_cliente", "contacto_cliente_mail",
        "tipo_robot", "usa_orquestador", "escalable", "version_plataforma", "ambiente_produccion",
        "prerequisitos_ejecutar", "datos_entrada", "datos_salida", "como_empezar", "reportes",
        "uso_orquestador", "politica_contrasenas", "credenciales_guardadas", "lista_queues",
        "detalles_calendario", "multiples_resoluciones", "resolucion_recomendada", "ambiente_desarrollo",
        "prerequisito_ambiente", "repositorios", "metodo_configuracion", "componentes_reutilizados",
        "nuevos_componentes", "seguimiento_ejecuciones", "tips_soporte",
    ]
    for clave in escalares:
        if clave in plano and isinstance(plano[clave], (dict, list)):
            plano[clave] = _texto_aplicaciones(plano[clave]) if clave in {"ambiente_produccion", "como_empezar"} else _texto(plano[clave])

    if isinstance(plano.get("mejoras_futuras"), list):
        plano["mejoras_futuras"] = [_texto(x) for x in plano["mejoras_futuras"] if _texto(x)]
    if isinstance(plano.get("supuestos"), list):
        plano["supuestos"] = [_texto(x) for x in plano["supuestos"] if _texto(x)]
    if isinstance(plano.get("preguntas_abiertas"), list):
        plano["preguntas_abiertas"] = [_texto(x) for x in plano["preguntas_abiertas"] if _texto(x)]
    return plano


def _buscar_item(lista, *claves_item: str) -> str:
    """Busca en una lista de {'item'/'nombre': ..., 'descripcion': ...} el
    valor cuyo 'item' matchea (case-insensitive, substring) alguna de las
    claves dadas, y devuelve su 'descripcion'."""
    if not isinstance(lista, list):
        return ""
    for entrada in lista:
        if not isinstance(entrada, dict):
            continue
        nombre_item = (entrada.get("item") or entrada.get("nombre") or entrada.get("titulo") or "").strip().lower()
        for clave in claves_item:
            if clave.lower() in nombre_item:
                return entrada.get("descripcion", "")
    return ""


def _recolectar_pares(nodo, pares: list, profundidad: int = 0) -> None:
    """Recorre todo el árbol JSON y junta pares (clave_normalizada, valor)
    de cada dict encontrado, sin importar en qué nivel de anidamiento
    esté. Se usa para ubicar campos del SDD sin depender de una ruta fija,
    porque en la práctica la Gem envuelve la respuesta de formas distintas
    en cada generación (a veces todo bajo 'documento', otras veces en
    claves hermanas tipo 'seccion_3_contactos', etc.)."""
    if profundidad > 6 or not isinstance(nodo, dict):
        return
    for k, v in nodo.items():
        clave = re.sub(r"^seccion_\d+_", "", k.strip().lower())
        pares.append((clave, v))
        if isinstance(v, dict):
            _recolectar_pares(v, pares, profundidad + 1)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    _recolectar_pares(item, pares, profundidad + 1)


def _find(pares: list, *substrings: str):
    """Devuelve el primer valor cuya clave (normalizada) contenga alguno
    de los substrings dados, probando los substrings en orden."""
    for s in substrings:
        for k, v in pares:
            if s in k:
                return v
    return None


def _buscar_lista_por_etiqueta(pares: list, *etiquetas: str):
    """Encuentra una lista de filas item/descripcion identificando sus etiquetas."""
    etiquetas = tuple(e.lower() for e in etiquetas)
    for clave, valor in pares:
        if not isinstance(valor, list) or not valor:
            continue
        etiquetas_en_lista = []
        for item in valor:
            if isinstance(item, dict):
                etiqueta = _texto(item.get("item") or item.get("nombre") or item.get("titulo") or item.get("campo"))
                if etiqueta:
                    etiquetas_en_lista.append(etiqueta.lower())
        if any(any(e in etiqueta for e in etiquetas) for etiqueta in etiquetas_en_lista):
            return valor
    return None


def _normalizar_wrapper(data: dict) -> dict:
    """Si el modelo no devolvió el esquema plano esperado (campos como
    'nombre_robot', 'archivos_flujo' o 'packages' en la raíz del JSON) sino
    que envolvió/repartió la respuesta en claves contenedoras (ej.
    'documento', 'seccion_3_contactos', 'seccion_9_gestion_excepciones',
    con nombres y formas que además varían de una generación a otra), esta
    función busca los datos por parecido de nombre en cualquier parte del
    árbol y arma el esquema plano que espera export_service. No modifica
    'data' si ya viene correctamente en formato plano."""
    if data.get("nombre_robot") or data.get("archivos_flujo") or data.get("packages"):
        # Aunque el esquema sea plano, algunos campos pueden venir como
        # listas/dicts. Siempre saneamos antes de entregarlo al exportador.
        return _sanear_plano(dict(data))

    pares: list = []
    _recolectar_pares(data, pares)
    if not pares:
        return data

    plano = dict(data)

    plano["nombre_robot"] = (
        _find(pares, "nombre_bot", "nombre_robot", "nombre_proceso") or plano.get("nombre_robot", "")
    )
    if isinstance(plano["nombre_robot"], (dict, list)):
        plano["nombre_robot"] = _texto(plano["nombre_robot"])

    historial = _find(pares, "historial_revisiones")
    if isinstance(historial, list) and historial and isinstance(historial[0], dict):
        h0 = historial[0]
        plano["revision"] = {
            "fecha": h0.get("fecha", ""),
            "version": h0.get("version", "1.0"),
            "descripcion": h0.get("descripcion", "Primera versión del documento"),
            "autor": h0.get("autor", ""),
            "revisor": h0.get("revisor", ""),
            "aprobador": h0.get("aprobador", ""),
            "cargo": h0.get("cargo", ""),
        }

    introduccion = _find(pares, "introduccion", "resumen_ejecutivo")
    if introduccion:
        plano["introduccion"] = _texto(introduccion) or plano.get("introduccion", "")

    # Objetivos: solo usar el campo objetivo/objetivos. No mezclar dentro/fuera
    # de alcance en esta sección porque el template los trata conceptualmente
    # como información distinta. Si la Gem no los devuelve, usamos una frase
    # derivada de la introducción como fallback legible.
    objetivos = _find(pares, "objetivos", "objetivo")
    if objetivos:
        plano["objetivos"] = _texto(objetivos)
    elif not plano.get("objetivos") and plano.get("introduccion"):
        plano["objetivos"] = plano["introduccion"]

    contactos = _find(pares, "contactos")
    if isinstance(contactos, list):
        for c in contactos:
            if not isinstance(c, dict):
                continue
            rol = (c.get("rol") or "").lower()
            if "analista" in rol:
                plano["contacto_analista"] = c.get("nombre", "")
                plano["contacto_analista_mail"] = c.get("email", "")
            elif "desarroll" in rol:
                plano["contacto_dev"] = c.get("nombre", "")
                plano["contacto_dev_mail"] = c.get("email", "")
            elif "cliente" in rol or "referente" in rol:
                plano["contacto_cliente"] = c.get("nombre", "")
                plano["contacto_cliente_mail"] = c.get("email", "")

    detalles_proceso = _find(pares, "detalles_proceso")
    if not isinstance(detalles_proceso, list):
        detalles_proceso = _buscar_lista_por_etiqueta(pares, "tipo de robot", "¿se usa orquestador?", "escalable")
    if isinstance(detalles_proceso, list):
        plano["tipo_robot"] = _buscar_item(detalles_proceso, "tipo de robot") or plano.get("tipo_robot", "")
        plano["usa_orquestador"] = _buscar_item(detalles_proceso, "orquestador") or plano.get("usa_orquestador", "")
        plano["escalable"] = _buscar_item(detalles_proceso, "escalable") or plano.get("escalable", "")
        plano["version_plataforma"] = (
            _buscar_item(detalles_proceso, "versión de", "version de", "plataforma")
            or plano.get("version_plataforma", "")
        )

    detalles_ejecucion = _find(pares, "detalles_ejecucion")
    if not isinstance(detalles_ejecucion, list):
        detalles_ejecucion = _buscar_lista_por_etiqueta(
            pares, "¿cómo empezar", "datos de entrada", "datos de salida", "pre-requisito", "reportes"
        )
    if isinstance(detalles_ejecucion, list):
        # Mapear cada fila del template por su etiqueta. No volcar la lista
        # completa dentro de "como_empezar" porque puede contener aplicaciones.
        mapeos = {
            "ambiente_produccion": ("ambiente de producción", "detalle del ambiente", "ambiente"),
            "prerequisitos_ejecutar": ("pre-requisito", "prerrequisito", "prerequisito", "requisito"),
            "datos_entrada": ("datos de entrada", "entrada"),
            "datos_salida": ("datos de salida", "salida esperada", "salidas"),
            "como_empezar": ("cómo empezar", "como empezar", "inicio del proceso", "disparador", "trigger"),
            "reportes": ("reportes", "reportes y salidas", "salida"),
            "uso_orquestador": ("cómo es usado el orquestador", "como es usado el orquestador", "uso del orquestador"),
            "politica_contrasenas": ("política de contraseñas", "politica de contrasenas", "contraseñas", "contrasenas"),
            "credenciales_guardadas": ("credenciales guardadas", "credenciales"),
            "lista_queues": ("lista de queues", "queues", "colas"),
            "detalles_calendario": ("detalles del calendario", "calendario", "frecuencia", "horario"),
            "multiples_resoluciones": ("múltiples resoluciones", "multiples resoluciones", "resoluciones soportadas"),
            "resolucion_recomendada": ("resolución recomendada", "resolucion recomendada"),
        }
        for entrada in detalles_ejecucion:
            if not isinstance(entrada, dict):
                continue
            etiqueta = _texto(entrada.get("item") or entrada.get("nombre") or entrada.get("titulo") or entrada.get("campo")).lower()
            valor = entrada.get("descripcion")
            if valor is None:
                valor = entrada.get("valor") or entrada.get("detalle") or entrada.get("contenido")
            for destino, aliases in mapeos.items():
                if any(alias in etiqueta for alias in aliases):
                    if destino == "ambiente_produccion" and isinstance(valor, list):
                        valor = _texto_aplicaciones(valor)
                    plano[destino] = _texto_aplicaciones(valor) if destino == "ambiente_produccion" else _texto(valor)
                    break
        # Algunas generaciones ponen las aplicaciones directamente bajo una
        # clave "aplicaciones". Eso pertenece al ambiente, no al disparador.
        aplicaciones = _find(pares, "aplicaciones")
        if aplicaciones and not plano.get("ambiente_produccion"):
            plano["ambiente_produccion"] = _texto_aplicaciones(aplicaciones)

        # Variante observada: una fila "Aplicaciones usadas" contiene la lista.
        if not plano.get("ambiente_produccion"):
            for entrada in detalles_ejecucion:
                if not isinstance(entrada, dict):
                    continue
                etiqueta = _texto(entrada.get("item") or entrada.get("nombre") or entrada.get("titulo") or "").lower()
                if "aplicacion" in etiqueta:
                    valor = entrada.get("descripcion") or entrada.get("valor") or entrada.get("detalle")
                    if isinstance(valor, list):
                        plano["ambiente_produccion"] = _texto_aplicaciones(valor)
                    else:
                        plano["ambiente_produccion"] = _texto(valor)
                    break

    # 'detalles_desarrollo' puede ser un dict con strings sueltos (formato 1)
    # o un dict cuyos valores son a su vez listas de item/descripcion
    # (formato 2, ej. "ambiente": [{"item": "Ambiente de Desarrollo", ...}]).
    desarrollo = _find(pares, "detalles_desarrollo")
    if isinstance(desarrollo, dict):
        ambiente = desarrollo.get("ambiente")
        if isinstance(ambiente, list):
            plano["ambiente_desarrollo"] = _buscar_item(ambiente, "desarrollo") or plano.get("ambiente_desarrollo", "")
            plano["ambiente_produccion"] = _buscar_item(ambiente, "producci") or plano.get("ambiente_produccion", "")
        elif ambiente:
            plano["ambiente_desarrollo"] = ambiente

        pre_requisitos = desarrollo.get("pre_requisitos") or desarrollo.get("prerrequisitos")
        plano["prerequisito_ambiente"] = _texto(pre_requisitos) or plano.get("prerequisito_ambiente", "")
        plano["prerequisitos_ejecutar"] = plano.get("prerequisitos_ejecutar") or _texto(pre_requisitos)

        plano["repositorios"] = _texto(desarrollo.get("repositorios")) or plano.get("repositorios", "")
        metodo_config = desarrollo.get("metodo_de_configuracion") or desarrollo.get("metodo_configuracion")
        plano["metodo_configuracion"] = _texto(metodo_config) or plano.get("metodo_configuracion", "")
        plano["componentes_reutilizados"] = (
            _texto(desarrollo.get("componentes_reutilizados")) or plano.get("componentes_reutilizados", "")
        )
        nuevos_comp = desarrollo.get("nuevos_componentes_reutilizables") or desarrollo.get("nuevos_componentes")
        plano["nuevos_componentes"] = _texto(nuevos_comp) or plano.get("nuevos_componentes", "")

    packages = _find(pares, "packages")
    if isinstance(packages, list):
        plano["packages"] = packages

    archivos = _find(pares, "archivos_de_flujo", "archivos_flujo")
    if isinstance(archivos, list):
        plano["archivos_flujo"] = archivos

    # Seguimiento: puede venir como lista plana de item/descripcion, o como
    # dict con 'ejecuciones'/'tips_soporte' separados.
    seguimiento = _find(pares, "seguimiento")
    if isinstance(seguimiento, list):
        plano["seguimiento_ejecuciones"] = _texto(seguimiento) or plano.get("seguimiento_ejecuciones", "")
    elif isinstance(seguimiento, dict):
        plano["seguimiento_ejecuciones"] = _texto(seguimiento.get("ejecuciones")) or plano.get("seguimiento_ejecuciones", "")
        plano["tips_soporte"] = _texto(seguimiento.get("tips_soporte")) or plano.get("tips_soporte", "")

    # Excepciones: distintas variantes de nombres de clave según la
    # generación ('negocio'/'sistema' o 'excepciones_de_negocio'/
    # 'excepciones_de_sistema'), y de campos dentro de cada excepción
    # ('excepcion'/'nombre', 'accion'/'tipo').
    excepciones = _find(pares, "gestion_excepciones", "excepciones")
    if isinstance(excepciones, dict):
        lineas = []
        negocio = excepciones.get("excepciones_de_negocio") or excepciones.get("negocio") or []
        sistema = excepciones.get("excepciones_de_sistema") or excepciones.get("sistema") or []
        for exc in negocio:
            if isinstance(exc, dict):
                nombre_exc = exc.get("excepcion") or exc.get("nombre") or ""
                accion_exc = exc.get("accion_a_realizar") or exc.get("accion") or ""
                lineas.append(f"[Negocio] {nombre_exc}: {accion_exc}")
        for exc in sistema:
            if isinstance(exc, dict):
                nombre_exc = exc.get("excepcion") or exc.get("nombre") or exc.get("tipo") or ""
                accion_exc = exc.get("accion_a_ejecutar") or exc.get("accion") or ""
                lineas.append(f"[Sistema] {nombre_exc}: {accion_exc}")
        if lineas:
            plano["tips_soporte"] = ((plano.get("tips_soporte") or "") + "\n" + "\n".join(lineas)).strip()

    supuestos = _find(pares, "consideraciones_supuestos", "supuestos")
    if isinstance(supuestos, list) and not plano.get("supuestos"):
        extraidos = []
        for s in supuestos:
            if isinstance(s, dict):
                extraidos.append(s.get("descripcion") or s.get("item") or "")
            else:
                extraidos.append(str(s))
        plano["supuestos"] = [s for s in extraidos if s]

    recursos = _find(pares, "recursos_externos")
    if isinstance(recursos, list):
        plano["recursos_externos"] = [
            {
                "recurso": r.get("recurso_web") or r.get("recurso", ""),
                "web": r.get("web", ""),
                "descripcion": r.get("descripcion", ""),
            }
            for r in recursos if isinstance(r, dict)
        ]

    glosario = _find(pares, "glosario")
    if isinstance(glosario, list):
        plano["glosario"] = glosario

    if not plano.get("introduccion"):
        titulo = _find(pares, "titulo")
        proyecto = _find(pares, "proyecto")
        if titulo:
            plano["introduccion"] = f"{titulo} — proyecto {proyecto or ''}".strip(" —")

    return _sanear_plano(plano)


class SddService:

    @staticmethod
    def parsear(texto_respuesta: str) -> dict:
        limpio = re.sub(r"^```(?:json)?|```$", "", texto_respuesta.strip(), flags=re.MULTILINE).strip()

        data = None
        try:
            data = json.loads(limpio)
        except (json.JSONDecodeError, TypeError):
            match = re.search(r"\{.*\}", texto_respuesta, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except (json.JSONDecodeError, TypeError):
                    data = None

        if not isinstance(data, dict):
            esqueleto = json.loads(json.dumps(_ESQUELETO_VACIO))
            esqueleto["introduccion"] = (
                "La Gem SDD no devolvió una estructura JSON válida. Revisar la respuesta de la Gem y volver a generar el documento."
            )
            esqueleto["preguntas_abiertas"] = ["La respuesta de la Gem SDD no pudo interpretarse como JSON válido."]
            return esqueleto

        data = _normalizar_wrapper(data)

        for k, v in _ESQUELETO_VACIO.items():
            data.setdefault(k, v)
        if not isinstance(data.get("revision"), dict):
            data["revision"] = _ESQUELETO_VACIO["revision"]
        else:
            for k, v in _ESQUELETO_VACIO["revision"].items():
                data["revision"].setdefault(k, v)
        return data

    @staticmethod
    def resumen_legible(data: dict) -> str:
        """Texto corto para la pestaña de Resultados, sin volcar el JSON crudo."""
        lineas = [f"SDD — {data.get('nombre_robot') or '(sin nombre)'}", ""]
        if data.get("introduccion"):
            lineas.append(data["introduccion"])
        lineas.append(f"\nArchivos de flujo definidos: {len(data.get('archivos_flujo', []))}")
        lineas.append(f"Packages/activities: {len(data.get('packages', []))}")
        lineas.append(f"Componentes reutilizados: {data.get('componentes_reutilizados') or '—'}")
        if data.get("supuestos"):
            lineas.append("\nSupuestos:")
            lineas += [f"  · {s}" for s in data["supuestos"]]
        if data.get("preguntas_abiertas"):
            lineas.append("\nPreguntas abiertas:")
            lineas += [f"  · {s}" for s in data["preguntas_abiertas"]]
        return "\n".join(lineas)
