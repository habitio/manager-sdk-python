import logging
from base import python_logging as pl
from base.settings import Settings

settings = Settings()


def get_real_logger_level(level):
    return 100 + 9 - level


class LoggerBase(logging.Logger):

    def __init__(self, name, *args, **kwargs):
        self.name = name
        self._log_type = kwargs.get('log_type', 'json')
        super().__init__(name, *args, **kwargs)

    @property
    def log_type(self):
        return self._log_type

    @log_type.setter
    def log_type(self, value: str):
        self._log_type = value


log_level = get_real_logger_level(int(settings.config_log["level"]))
pl.setup_loglevel()
log_type = settings.config_log.get('format', 'json')
host_pub = settings.host_pub
logger_handler = pl.setup_logger_handler(settings.log_path, log_level, log_type, host_pub)
logging.setLoggerClass(LoggerBase)

logger = logging.getLogger(__name__)
logger.log_type = log_type
logger.addHandler(logger_handler)

LOG_TABLE = {
            0: logger.emergency,
            1: logger.alert,
            2: logger.critical,
            3: logger.error,
            4: logger.warning,
            5: logger.notice,
            6: logger.info,
            7: logger.debug,
            8: logger.trace,
            9: logger.verbose
        }
