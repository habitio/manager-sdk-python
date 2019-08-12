try:
    import uwsgi
except ModuleNotFoundError:
    pass
import json
import logging.handlers
import time
from functools import wraps


log_levels = {
    "EMERGENCY": ["\x1B[4;31m emergency \x1B[0m ", 109],
    "ALERT": ["\x1B[4;31m   alert   \x1B[0m ", 108],
    "CRITICAL": ["\x1B[4;35m critical  \x1B[0m ", 107],
    "ERROR": ["\x1B[4;35m   error   \x1B[0m ", 106],
    "WARNING": ["\x1B[4;35m  warning  \x1B[0m ", 105],
    "NOTICE": ["\x1B[4;36m  notice   \x1B[0m ", 104],
    "INFO": ["\x1B[4;37m   info    \x1B[0m ", 103],
    "DEBUG": ["\x1B[4;33m   debug   \x1B[0m ", 102],
    "TRACE": ["\x1B[4;32m   trace   \x1B[0m ", 101],
    "VERBOSE": ["\x1B[4;32m  verbose  \x1B[0m ", 100]
}


class CustomFormatter(logging.Formatter):

    def __init__(self, fmt=None, datefmt=None, style='%', log_type='json') -> None:
        self._log_type = log_type
        super().__init__(fmt, datefmt, style)

    @property
    def log_type(self) -> str:
        return self._log_type

    @log_type.setter
    def log_type(self, value) -> None:
        self._log_type = value

    def formatTime(self, record, datefmt=None) -> [float, str]:
        if self.log_type == 'json':
            return round(float(record.created), 3)
        else:
            return super().formatTime(record, datefmt)


def update_log_level(func):
    @wraps(func)
    def update_level(self, message, *args, **kwargs) -> func:
        try:
            shared_log_level = uwsgi.sharedarea_read(0, 3, 3)
            shared_timestamp = uwsgi.sharedarea_read(0, 6).decode('ascii').strip().strip('\x00')
            global_level = int(shared_log_level.decode('ascii'))
            global_timestamp = int(shared_timestamp)
            if 0 < global_timestamp < int(time.time()):
                default_log_level = uwsgi.sharedarea_read(0, 0, 3)
                global_level = int(default_log_level.decode('ascii'))
                memory_length = len(uwsgi.sharedarea_memoryview(0))
                uwsgi.sharedarea_write(0, 3, json.dumps(global_level))
                uwsgi.sharedarea_write(0, 6, (json.dumps(0) + (memory_length - 7)*'\x00'))
        except NameError:
            global_level = self.level
        if self.level != global_level:
            self.setLevel(global_level)
        return func(self, message, *args, **kwargs)

    return update_level


def format_message(func):
    @wraps(func)
    def message_replace(self, message, *args, **kwargs) -> func:
        if hasattr(self, 'log_type') and self.log_type == 'json':
            if not type(message) is str:
                message = json.dumps(message)
            message = message.replace('\n', '\\n')
            message = message.replace('\t', '\\t')
            message = message.replace('"', '\\"')
            message = message.replace("'", "\\'")
        return func(self, message, *args, **kwargs)

    return message_replace


def get_log_kwargs(log_level: int) -> dict:
    kwargs = {
        'extra': {'zptLogLevel': 109 - log_level},
        'exc_info': True if log_level == 101 else None
    }
    return kwargs


@update_log_level
@format_message
def verbose(self, message, *args, **kws) -> None:
    # Yes, logger takes its "*args" as "args".

    log_level = log_levels["VERBOSE"][1]
    if self.isEnabledFor(log_level):
        kws = get_log_kwargs(log_level)
        self._log(log_level, message, args, **kws)


@update_log_level
@format_message
def trace(self, message, *args, **kws) -> None:
    # Yes, logger takes its "*args" as "args".

    log_level = log_levels["TRACE"][1]
    if self.isEnabledFor(log_level):
        kws = get_log_kwargs(log_level)
        self._log(log_level, message, args, **kws)


@update_log_level
@format_message
def debug(self, message, *args, **kws) -> None:
    # Yes, logger takes its "*args" as "args".

    log_level = log_levels["DEBUG"][1]
    if self.isEnabledFor(log_level):
        kws = get_log_kwargs(log_level)
        self._log(log_level, message, args, **kws)


@update_log_level
@format_message
def info(self, message, *args, **kws) -> None:
    # Yes, logger takes its "*args" as "args".

    log_level = log_levels["INFO"][1]
    if self.isEnabledFor(log_level):
        kws = get_log_kwargs(log_level)
        self._log(log_level, message, args, **kws)


@update_log_level
@format_message
def notice(self, message, *args, **kws) -> None:
    # Yes, logger takes its "*args" as "args".

    log_level = log_levels["NOTICE"][1]
    if self.isEnabledFor(log_level):
        kws = get_log_kwargs(log_level)
        self._log(log_level, message, args, **kws)


@update_log_level
@format_message
def warning(self, message, *args, **kws) -> None:
    # Yes, logger takes its "*args" as "args".

    log_level = log_levels["WARNING"][1]
    if self.isEnabledFor(log_level):
        kws = get_log_kwargs(log_level)
        self._log(log_level, message, args, **kws)


@update_log_level
@format_message
def error(self, message, *args, **kws) -> None:
    # Yes, logger takes its "*args" as "args".

    log_level = log_levels["ERROR"][1]
    if self.isEnabledFor(log_level):
        kws = get_log_kwargs(log_level)
        self._log(log_level, message, args, **kws)


@update_log_level
@format_message
def critical(self, message, *args, **kws) -> None:
    # Yes, logger takes its "*args" as "args".

    log_level = log_levels["CRITICAL"][1]
    if self.isEnabledFor(log_level):
        kws = get_log_kwargs(log_level)
        self._log(log_level, message, args, **kws)


@update_log_level
@format_message
def alert(self, message, *args, **kws) -> None:
    # Yes, logger takes its "*args" as "args".

    log_level = log_levels["ALERT"][1]
    if self.isEnabledFor(log_level):
        kws = get_log_kwargs(log_level)
        self._log(log_level, message, args, **kws)


@update_log_level
@format_message
def emergency(self, message, *args, **kws) -> None:
    # Yes, logger takes its "*args" as "args".

    if self.isEnabledFor(log_levels["EMERGENCY"][1]):
        self._log(log_levels["EMERGENCY"][1], message, args, **kws)


def setup_logger_handler(log_path, log_level, log_type, host_pub) -> logging.handlers:
    # Create the Handler for logging data to a file
    if log_path == "/var/log/syslog":
        logger_handler = logging.handlers.SysLogHandler(address="/dev/log")
    else:
        logger_handler = logging.FileHandler(log_path)

    # Create a Formatter for formatting the log messages
    if log_type == 'pretty':
        logger_formatter = CustomFormatter("%(levelname)s | \x1B[1;37m%(asctime)s\x1B[0m | %(message)s | "
                                           "%(processName)s:%(process)d %(filename)s:%(lineno)d ",
                                           datefmt="%Y-%m-%d %H:%M:%S",
                                           log_type=log_type)
    else:
        logger_formatter = CustomFormatter("{\"version\":\"1.1\","
                                           "\"host\":\""+host_pub+"\","
                                           "\"source\":\"%(filename)s\","
                                           "\"short_message\":\"%(message)s\","
                                           "\"timestamp\":%(asctime)s,"
                                           "\"level\":%(zptLogLevel)s,"
                                           "\"pid\":%(process)d,"
                                           "\"exec\":\"%(processName)s\","
                                           "\"file\":\"%(filename)s\","
                                           "\"line\":%(lineno)d}",
                                           datefmt="",
                                           log_type=log_type)

    # Adding Formatter to the Handler
    logger_handler.setFormatter(logger_formatter)

    # Setting Level to the handler
    logger_handler.setLevel(log_level)

    return logger_handler


def setup_loglevel() -> None:
    for lvl in log_levels.keys():
        logging.addLevelName(log_levels[lvl][0], log_levels[lvl][1])

    logging.Logger.verbose = verbose
    logging.Logger.trace = trace
    logging.Logger.debug = debug
    logging.Logger.info = info
    logging.Logger.notice = notice
    logging.Logger.warning = warning
    logging.Logger.error = error
    logging.Logger.critical = critical
    logging.Logger.alert = alert
    logging.Logger.emergency = emergency


