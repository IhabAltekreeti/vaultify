from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect


db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = (
    "Please log in to access this page."
)
login_manager.login_message_category = "warning"

csrf = CSRFProtect()

migrate = Migrate()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
)
