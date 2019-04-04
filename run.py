import os
from base import settings
from base import logger
from flask import Flask

# Flask App
logger.verbose("Creating Flask Object...")

try:
    app = Flask(__name__, instance_relative_config=True)
    logger.info("[Boot]: Flask object successfully created!")
except Exception as ex:
    logger.emergency("[Boot]: Flask object creation failed!")
    logger.trace(ex)
    raise

app.config.from_object("flask_config")

try:
    from base import views
except Exception as ex:
    print('Error: {}'.format(ex))
    os._exit(1)

try:
    views = views.Views(app)
except Exception as ex:
    print('Error: {}'.format(ex))
    os._exit(1)

print('[Boot]: Views: OK')

print("__name__ = {}".format(__name__))

if __name__ == "__main__":
    try:
        print('[Boot]: Starting server...')
        app.run(port=settings.port)
    except Exception:
        print("********* Unknown Error! *********")
        raise
