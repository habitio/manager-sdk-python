from base.settings import settings
from base import logger
from flask import Flask
from flask_mqtt import Mqtt


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

from base import views
views = views.Views(app)



print("__name__ = "+__name__)
if __name__ == "__main__":
    try:
        # host="0.0.0.0"
        app.run(port=settings.port)
    except Exception:
        print("********* Unknown Error!!! ********")    
        raise