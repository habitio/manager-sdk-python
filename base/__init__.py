from flask import Flask
from flask_mqtt import Mqtt
from base import python_logging as pl
import logging

# Create the Logger
logger = logging.getLogger(__name__)

# Add the Handler to the Logger
logger.addHandler(pl.logger_handler)

logger.notice("\n\n\n"+"==="*45+"\n\n\n")
logger.info("Completed configuring logger!")
 
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


