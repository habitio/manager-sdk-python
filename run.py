from base.settings import settings
from base import logger
from flask import Flask
from flask_mqtt import Mqtt
from base import Views


# Flask App
logger.verbose("Creating Flask Object...")
try:
    logger.debug(" ************************ CREATE FLASK")

    app = Flask(__name__, instance_relative_config=True)
    logger.info("Flask object successfully created!")
except Exception as ex:
    logger.emergency("Flask object creation failed ...")
    logger.trace(ex)
    raise

app.config.from_object("flask_config")

logger.debug(" ************************ CALL VIEWS")
views = Views(app)

# from base import app

print("__name__ = "+__name__)
if __name__ == "__main__":
    try:
        # host="0.0.0.0"
        logger.debug(" ************************ RUN APP")

        app.run(port=settings.port)
    except Exception:
        print("********* Unknown Error!!! ********")    
        raise