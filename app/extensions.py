"""Extensiones de Flask compartidas por toda la aplicación."""
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Iniciá sesión para continuar."
login_manager.login_message_category = "warning"
login_manager.session_protection = "strong"

csrf = CSRFProtect()
