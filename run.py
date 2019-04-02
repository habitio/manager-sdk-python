print('[Boot]: Starting the process: OK')

print('[Boot]: Settings: Importing')
from base.settings import settings
print('[Boot]: Settings: OK')


print('[Boot]: Logs: Setting up')
from base import logger
print('[Boot]: Logs: OK')

print('[Boot]: Flask: Setting up')
from flask import Flask
from werkzeug.contrib.profiler import ProfilerMiddleware

print('[Boot]: Flask: OK')


# Flask App
logger.verbose("Creating Flask Object...")

try:
    app = Flask(__name__, instance_relative_config=True)
    print("[Boot]: Flask object successfully created!")
    logger.info("[Boot]: Flask object successfully created!")
except Exception as ex:
    print("[Boot]: Flask object creation failed!")
    print(ex)
    logger.emergency("[Boot]: Flask object creation failed!")
    logger.trace(ex)
    raise

print('[Boot]: Flask Config: Setting up')
app.config.from_object("flask_config")
print('[Boot]: Flask Config: OK')

print('[Boot]: Views: Setting up')

try:
    from base import views
except Exception as ex:
    print('Error: {}'.format(ex))
    exit()

try:
    views = views.Views(app)
except Exception as ex:
    print('Error: {}'.format(ex))
    exit()

print('[Boot]: Views: OK')

print("__name__ = {}".format(__name__))

if __name__ == "__main__":
    try:
        print('[Boot]: Starting server...')
        app.config['PROFILE'] = True
        app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30])
        app.run(port=settings.port, debug=True)

    except Exception:
        print("********* Unknown Error! *********")
        raise
