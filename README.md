# AutoDocs AI

Implementación de referencia del proyecto conceptual **AutoDocs AI**
(Trabajo de Medio Ciclo — UTN-FRBA / Epidata, "IA Aplicada a Organizaciones").

Automatiza el ciclo de preventa y relevamiento técnico de RPA/Hyperautomation:
a partir de una transcripción de relevamiento, orquesta el pool de Gems de
Gemini (Ingesta, PDD, SDD, QA, Estimación y Supervisor) para producir un
paquete documental completo (PDD, SDD, matriz de casos de prueba y planilla
de estimación) listo para revisión humana.

## Qué está desarrollado y qué no

Siguiendo el pedido del enunciado, esta implementación construye **toda la
conexión y orquestación** (validación de entrada, sanitización de PII,
memoria organizacional, llamadas a la API de Gemini, log de comunicación
agéntica, consolidación, exportación a Word/Excel), pero **no desarrolla el
razonamiento interno de las Gems** descriptas en el punto 4 del enunciado.
Cada Gem es, a nivel de código, el mismo modelo Gemini invocado con un
`system_instruction` configurable desde `/configuracion` — ahí es donde se
pega el prompt real de cada Gem una vez diseñado directamente en Gemini.

## Arquitectura

```
app.py                     # entry point
core/
  db.py                    # esquema SQLite (proyectos, documentos, logs, memoria)
  config_manager.py        # config de proveedor + Gems (sin lógica, solo conexión)
ai/
  provider_router.py
  providers/gemini_provider.py   # HTTP directo a la API de Gemini
repositories/
  proyecto_repository.py   # CRUD proyectos, documentos, logs, alertas
  memoria_repository.py    # memoria organizacional (largo plazo)
services/
  validacion_service.py    # Límite Operativo de Entrada (punto 7)
  pii_service.py            # sanitización PII → [MOCK_DATA] / [SISTEMA_COMPARTIDO]
  gems_service.py          # conexión con el pool de Gems (punto 4)
  memoria_service.py       # memoria corto/largo plazo (punto 6)
  consolidacion_service.py # apoyo al Agente Supervisor (punto 4/7)
  export_service.py        # PDD/SDD → .docx · QA/Estimación → .xlsx
pipeline/
  relevamiento_pipeline.py # ciclo cerrado: Observación→...→Aprendizaje (punto 5)
ui/
  app.py                   # rutas Flask
  templates/                # Dashboard, Nuevo Relevamiento, Procesamiento, Resultado, Memoria, Configuración
```

## Cómo correrlo

```bash
pip install -r requirements.txt
setx GOOGLE_API_KEY "tu-api-key-de-gemini"      # Windows
python app.py
```

Abrir `http://localhost:5002`. Podés usar `samples/transcripcion_ejemplo.txt`
para probar el circuito completo desde "Nuevo Relevamiento".

## Simplificaciones respecto del stack propuesto en el Trabajo de Medio Ciclo

- **Memoria de largo plazo**: SQLite con búsqueda por palabras clave en vez
  de PostgreSQL + pgvector con embeddings. La interfaz de
  `MemoriaService`/`MemoriaRepository` está pensada para que esa migración
  no impacte al resto del sistema.
- **Memoria de corto plazo**: vive en la fila de `proyectos` durante el
  ciclo, en vez de Redis.
- **Ejecución "paralela" de las Gems documentales**: en esta demo corre en
  secuencia (más simple de depurar); el punto de extensión para paralelizar
  con hilos/async o con LangGraph es `RelevamientoPipeline.procesar`.
