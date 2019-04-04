import os
from base import settings
from base import logger
from flask import Flask
from base import views

# Flask App
logger.verbose("Creating Flask Object...")

try:
    if not settings.mqtt:
        app = Flask(__name__, instance_relative_config=True)
        app.config.from_object("flask_config")
        views = views.Views(app)
        logger.info("[Boot]: Flask object successfully created!")
    else:
        app = views.Views()
        logger.info("[Boot]: Mqtt")


except Exception as ex:
    logger.emergency("[Boot]: Flask object creation failed!")
    logger.trace(ex)
    raise


print('[Boot]: Views: OK')
print("__name__ = {}".format(__name__))

if __name__ == "__main__":
    try:
        print('[Boot]: Starting server...')
        app.run(port=settings.port)
    except Exception:
        print("********* Unknown Error! *********")
        raise
