from base.settings import settings
from flask import Flask
from flask_mqtt import Mqtt
from base import logger


import sys
logger.debug("sys.path:" + sys.path)

# Flask App
logger.verbose("Creating Flask Object...")
try:
    app = Flask(__name__, instance_relative_config=True)
    logger.info("Flask object successfully created!")
except Exception as ex:
    logger.emergency("Flask object creation failed ...")
    logger.trace(ex)
    raise

app.config.from_object("flask_config")

print("__name__ = "+__name__)
if __name__ == "__main__":
    try:
        # host="0.0.0.0"
        app.run(port=settings.port)
    except Exception:
        print("********* Unknown Error!!! ********")    
        raise

from base import views