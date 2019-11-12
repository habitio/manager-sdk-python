import json
import threading
import time
from functools import wraps
from uuid import UUID
from typing import AnyStr
from base.exceptions import ValidationException


def format_response(resp):
    """
    Returns a str formatted response
    :param resp: Requests response
    :return: response text as a string, formatted as a json if valid
    """
    try:
        error_msg = format_str(resp.json(), is_json=True)
    except ValueError:  # requests returns a ValueError when resp.text is not a valid json
        error_msg = format_str(resp.text, is_json=False)
    return error_msg


def format_str(str_value, is_json):
    """
    Returns a formatted string with break lines; if is_json True, pretty format the output
    :param str_value: plain text or json value
    :param is_json: Boolean
    :return: str
    """
    str_value = json.dumps(str_value, indent=4, sort_keys=True) if is_json else str_value
    return '\n {} \n'.format(str_value)


def is_json(str_value):
    """A function to check if a string contains a valid json"""
    try:
        json.loads(str_value)
    except ValueError:
        return False
    return True


def rate_limited(max_per_second: int):
    """
        Rate-limits the decorated function locally, for one process.
        source: https://gist.github.com/gregburek/1441055#gistcomment-945625
    """
    lock = threading.Lock()
    min_interval = 1.0 / max_per_second

    def decorate(func):
        last_time_called = time.perf_counter()

        @wraps(func)
        def rate_limited_function(*args, **kwargs):
            lock.acquire()
            nonlocal last_time_called
            try:
                elapsed = time.perf_counter() - last_time_called
                left_to_wait = min_interval - elapsed
                if left_to_wait > 0:
                    time.sleep(left_to_wait)

                return func(*args, **kwargs)
            finally:
                last_time_called = time.perf_counter()
                lock.release()

        return rate_limited_function

    return decorate


def mask_token(token):
    return '{}...{}'.format(token[:8], token[-5:])


def synchronized(lock):
    """ Synchronization decorator. """

    def wrap(f):
        def newFunction(*args, **kw):
            lock.acquire()
            try:
                return f(*args, **kw)
            finally:
                lock.release()
        return newFunction
    return wrap


def get_real_logger_level(level) -> int:
    return 100 + 9 - level


def is_valid_uuid(uuid_: AnyStr):
    try:
        uuid_obj = UUID(uuid_)
        return str(uuid_obj) == uuid_
    except ValueError:
        return False
