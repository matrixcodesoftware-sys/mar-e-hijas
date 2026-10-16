"""Configuración de la aplicación. Todo valor sensible se lee de variables de entorno (.env)."""
import os
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _bool(nombre: str, defecto: str = "0") -> bool:
    return os.environ.get(nombre, defecto).strip().lower() in ("1", "true", "si", "sí", "yes")


class Config:
    APP_NOMBRE = "MAR E HIJAS"
    APP_SUBTITULO = "Sistema de Gestión de Áridos"

    SECRET_KEY = os.environ.get("SECRET_KEY", "")

    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_NAME = os.environ.get("DB_NAME", "mar_e_hijas")
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "America/Argentina/Buenos_Aires")
    ITEMS_POR_PAGINA = int(os.environ.get("ITEMS_POR_PAGINA", "25"))

    # Sesión y cookies
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=int(os.environ.get("SESION_MINUTOS", "480")))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE")
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE")

    # CSRF
    WTF_CSRF_TIME_LIMIT = None  # válido mientras dure la sesión
    WTF_CSRF_HEADERS = ["X-CSRFToken", "X-CSRF-Token"]

    MAX_CONTENT_LENGTH = 4 * 1024 * 1024

    FACTURACION_PROVEEDOR = os.environ.get("FACTURACION_PROVEEDOR", "ninguno")
    ARCA_CERT_PATH = os.environ.get("ARCA_CERT_PATH", "")
    ARCA_KEY_PATH = os.environ.get("ARCA_KEY_PATH", "")
    ARCA_PRODUCCION = _bool("ARCA_PRODUCCION")

    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", "1")
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE


def obtener_config():
    entorno = os.environ.get("FLASK_ENV", "development").lower()
    return ProductionConfig if entorno == "production" else DevelopmentConfig
