class Config:

    SECRET_KEY = 'chiave_segreta'

    DB_USER = 'postgres'
    DB_PASSWORD = '12345'
    DB_HOST = 'localhost'
    DB_NAME = 'aereidb'
    DB_PORT = '5432'
    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True
    PORT = 5000