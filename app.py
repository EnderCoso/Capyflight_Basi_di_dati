# -*- coding: utf-8 -*-

from flask import Flask
from flask_migrate import Migrate
from config import Config
from models import db
from routes import bp

def create_app():
    app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
    app.config.from_object(Config)
    db.init_app(app)
    Migrate(app, db)

    # Registra il blueprint
    app.register_blueprint(bp)

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
