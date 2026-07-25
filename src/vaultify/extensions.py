"""Shared Flask extensions for Vaultify.

These extension objects are intentionally created without binding them to a
Flask application. The application factory will initialize them later.
"""

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
