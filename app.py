"""
Punto de entrada principal — AutoDocs AI.
python-dotenv carga el .env ANTES de que cualquier módulo lea os.getenv().
(Misma arquitectura que Wine AI OS / Financial AI OS, portada sin cambios de fondo.)
"""
from dotenv import load_dotenv
load_dotenv(override=False)   # las vars del OS siempre ganan sobre .env

from core.db import init_db
init_db()

from ui.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5002)
