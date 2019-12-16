from base import settings
from base import logger
from flask import Flask
from flask_cors import CORS
from base.thread_pool import ThreadPool
from base.constants import DEFAULT_THREAD_POOL_LIMIT
if settings.config_thread_pool.get('enabled', True):
    thread_pool = ThreadPool(settings.config_thread_pool.get('num_threads', DEFAULT_THREAD_POOL_LIMIT))
    thread_pool.start()
else:
    thread_pool = None

from base import views
from base.common.tcp_base import TCPBase

# Flask App
logger.verbose("Creating Flask Object...")

try:
    if not settings.mqtt:
        app = Flask(__name__, instance_relative_config=True)
        app.config.from_object("flask_config")
        if settings.enable_cors is True:
            CORS(app, supports_credentials=True)
        views = views.Views(app, thread_pool)
        logger.info("[Boot]: Flask object successfully created!")
        if settings.config_tcp.get('enabled', False):
            tcp_ = TCPBase(webhook=views.webhook)
            tcp_.kickoff()
    else:
        app = views.Views()
        logger.info("[Boot]: Mqtt")

except Exception as ex:
    logger.emergency("[Boot]: Flask object creation failed!")
    logger.trace(ex)
    raise


print('[Boot]: Views: OK')
print("__name__ = {}".format(__name__))

if __name__ == "__main__":
    try:
        print('[Boot]: Starting server...')
        app.run(port=settings.port)
    except Exception:
        print("********* Unknown Error! *********")
        raise
