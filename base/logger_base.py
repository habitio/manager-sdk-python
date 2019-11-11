import logging
import time
import threading
from flask import Response, json, jsonify
from base import python_logging as pl
from base.settings import Settings
from base.exceptions import InvalidUsage
from base.utils import get_real_logger_level

settings = Settings()


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

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info,
                   func=None, extra=None, sinfo=None):
        fn = extra.pop('fn', fn)
        lno = extra.pop('lno', lno)
        func = extra.pop('func', func)
        return super().makeRecord(name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)


log_level = get_real_logger_level(int(settings.config_log["level"]))
try:
    import uwsgi

    uwsgi.sharedarea_write(0, 0, json.dumps(log_level))
    uwsgi.sharedarea_write(0, 3, json.dumps(log_level))
except ModuleNotFoundError:
    pass

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


def level_runtime(request) -> Response:

    if request.method == 'GET':
        try:
            shared_area = uwsgi.sharedarea_read(0, 3, 3)
            level = int(shared_area.decode('utf-8'))
        except:
            level = logger.level
        context = {
            "level_number": 109 - level
        }
        response = jsonify(context)
        response.status_code = 200

    elif request.method == 'POST':
        if request.is_json and request.data:
            payload = request.get_json()
            if 'level_number' not in payload:
                raise InvalidUsage(status_code=412, message='level_number not found in payload')
            elif type(payload['level_number']) is not int or not 0 <= payload['level_number'] <= 9:
                raise InvalidUsage(status_code=412, message='level_number is not a number or not between 0 and 9')
            else:
                level = payload.get('level_number', 9)
                real_level = int(get_real_logger_level(int(level)))
                expire_hours = payload.get('expire_hours', 0)
                expire_timestamp = int(time.time()) + int(float(expire_hours) * 3600) if expire_hours else 0
                payload = {
                    "level_number": level,
                    "expire_hours": expire_hours
                }
                try:
                    if expire_hours == 0:
                        uwsgi.sharedarea_write(0, 0, json.dumps(real_level))
                    else:
                        timer_thread = threading.Thread(target=set_global_log_level, args=(expire_timestamp,),
                                                        name='Timer',
                                                        daemon=True)
                        timer_thread.start()
                    uwsgi.sharedarea_write(0, 3, json.dumps(real_level))
                except NameError:
                    logger.setLevel(real_level)

                response = jsonify(payload)
                response.status_code = 200

        else:
            raise InvalidUsage('No data or data format invalid.', status_code=422)
    else:
        raise InvalidUsage('The method is not allowed for the requested URL.', status_code=405)

    return response


def set_global_log_level(expire_timestamp):
    timer_ = expire_timestamp - int(time.time())
    time.sleep(int(timer_))
    try:
        default_log_level = uwsgi.sharedarea_read(0, 0, 3)
        global_level = int(default_log_level.decode('ascii'))
        uwsgi.sharedarea_write(0, 3, json.dumps(global_level))
    except NameError:
        pass
