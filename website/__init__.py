# import flask - from 'package' import 'Class'
from flask import Flask 
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy import event, MetaData
from sqlalchemy.engine import Engine


convention = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=convention))
migrate = Migrate(compare_type=True, compare_server_default=True)

# turn on foreign key constraints so certain rules can operate
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    try:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass

# create a function that creates a web application
# a web server will run this web application
def create_app():
  
    app = Flask(__name__)  # this is the name of the module/package that is calling this app
    # Should be set to false in a production environment
    app.debug = True
    app.secret_key = 'somesecretkey'
    # set the app configuration data 
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sitedata.sqlite'
    # turn off deprecation warnings
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # initialise db with flask app
    db.init_app(app)
    # import all models before starting the Flask-Migrate
    from . import models
    migrate.init_app(app, db, render_as_batch=True)
    #create the db tables and add tags. uncomment if you make changes to models.py
    # '''with app.app_context():
    #   from . import models
    #   db.create_all()
    #   from .models import Tag
    #   tag1 = Tag(name="Tech & AI")
    #   tag2 = Tag(name="Marketing")
    #   tag3 = Tag(name="Finance")
    #   tag4 = Tag(name="Health")
    #   tag5 = Tag(name="Education")
    #   db.session.add_all([tag1, tag2, tag3, tag4, tag5])
    #   db.session.commit()'''
    Bootstrap5(app)
    
    # initialise the login manager
    login_manager = LoginManager()
    
    # set the name of the login function that lets user login
    # in our case it is auth.login (blueprintname.viewfunction name)
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)
    # create a user loader function takes userid and returns User
    # Importing inside the create_app function avoids circular references
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
       return db.session.scalar(db.select(User).where(User.id==user_id))

    from . import views
    app.register_blueprint(views.main_bp)

    from . import auth
    app.register_blueprint(auth.auth_bp)

    from . import bookings
    app.register_blueprint(bookings.bookings_bp)
    
    return app