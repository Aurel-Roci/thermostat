from flask import Flask
from flask_influxdb import InfluxDB
import settings

influx_db = InfluxDB()


def create_app(testing=False):

    app = Flask(__name__)
    # app.config.from_object("config.DevelopmentConfig")
    with app.app_context():

        from app import views

        influx_db.init_app(app=app)
        from app import database
        db = database.Database()
        from app import humidity
        sensor = humidity.Sensor(db)
        sensor.get_data()

    return app
