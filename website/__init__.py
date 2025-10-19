# import flask - from 'package' import 'Class'
from flask import Flask 
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
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
    # import all models
    from . import models
    #create the db tables and add tags. uncomment if you make changes to models.py
    with app.app_context():
        from . import models
        db.create_all()   
        _ensure_sqlite_column(
            db.engine,
            table="events",
            column="is_active",
            ddl="ALTER TABLE events ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
        )
      
        from .models import Tag
        tag1 = Tag(name="Tech & AI")
        tag2 = Tag(name="Marketing")
        tag3 = Tag(name="Finance")
        tag4 = Tag(name="Health")
        tag5 = Tag(name="Education")

        # fix for tags breaking on startup
        tags_array = [tag1, tag2, tag3, tag4, tag5]

        for each in tags_array:
            # check if each tag exists
            check_existing = db.session.execute(db.select(Tag).where(Tag.name == each.name)).scalar()

            if app.debug == True:
                print("Tag check: " + str(check_existing))

            # if it doesn't, add it
            if check_existing == None:
                if app.debug == True:
                    print("Tag added: " + str(each))
                #add_tag = Tag(name = each)
                db.session.add(each)

        #db.session.add_all([tag1, tag2, tag3, tag4, tag5])
        db.session.commit()
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

        from . import events
        app.register_blueprint(events.events_bp)
        
        return app