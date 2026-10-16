"""Punto de entrada.

Desarrollo:   python run.py            (servidor de Flask con recarga automática)
Producción:   python run.py --prod     (servidor Waitress, apto para Windows y Linux)
              o con gunicorn en Linux:  gunicorn -w 3 -b 0.0.0.0:8000 "run:app"
"""
import os
import sys

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    if "--prod" in sys.argv:
        from waitress import serve

        print(f"MAR E HIJAS sirviendo en http://{host}:{port} (waitress)")
        serve(app, host=host, port=port, threads=8)
    else:
        app.run(host=host, port=port, debug=app.config.get("DEBUG", False))
