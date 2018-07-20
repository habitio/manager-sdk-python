from base import python_logging as pl
import logging

# Create the Logger
logger = logging.getLogger(__name__)

# Add the Handler to the Logger
logger.addHandler(pl.logger_handler)

logger.notice("\n\n\n"+"==="*45+"\n\n\n")
logger.info("Completed configuring logger!")