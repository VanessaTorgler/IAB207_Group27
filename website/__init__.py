# import flask - from 'package' import 'Class'
from flask import Flask
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from sqlalchemy import event, MetaData, inspect
from sqlalchemy.engine import Engine

convention = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=convention))

# Enable CSRF for Flask‑WTF forms
csrf = CSRFProtect()

# turn on foreign key constraints so certain rules can operate
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    try:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass

def _ensure_sqlite_column(engine, table: str, column: str, ddl: str):
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns(table)}
    if column not in cols:
        with engine.begin() as conn:
            conn.exec_driver_sql(ddl)

# App factory: enable CSRF and register bookings blueprint (no other changes).
def create_app():
    app = Flask(__name__)
    app.debug = True
    app.secret_key = 'somesecretkey'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sitedata.sqlite'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # init extensions
    db.init_app(app)
    csrf.init_app(app)
    Bootstrap5(app)

    # import models so tables are known
    from . import models

    with app.app_context():
        db.create_all()
        _ensure_sqlite_column(
            db.engine,
            table="events",
            column="is_active",
            ddl="ALTER TABLE events ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
        )

        # seed Tags if missing
        from .models import Tag
        for name in ["Tech & AI", "Marketing", "Finance", "Health", "Education"]:
            exists = db.session.execute(db.select(Tag).where(Tag.name == name)).scalar()
            if not exists:
                db.session.add(Tag(name=name))
        db.session.commit()

    # Login manager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.scalar(db.select(User).where(User.id == user_id))

    # Blueprints
    from . import views
    app.register_blueprint(views.main_bp)

    from . import auth
    app.register_blueprint(auth.auth_bp)

    # Your repo already has bookings.py — register its blueprint
    from . import bookings
    app.register_blueprint(bookings.bookings_bp)

    from . import events
    app.register_blueprint(events.events_bp)
    
    from .forms import LogoutForm
    from .forms import EventActionForm
    @app.context_processor
    def inject_logout_form():
        return {
            "logout_form": LogoutForm(),
            "event_action_form": EventActionForm(),
        }

    # (If you keep custom 404s elsewhere, you can still register them here)
    try:
        from .templates.error import page_not_found
        app.register_error_handler(404, page_not_found)
    except Exception:
        pass

    return app