import os
print('[Solid]: Settings: Setting up')
from base import settings
print('[Solid]: Settings: OK')


print('[Solid]: ImportLib::Utils: Setting up')
from importlib import util
print('[Solid]: ImportLib::Utils: OK')

print('[Solid]: Inspect and Logging: Setting up')
import inspect, traceback
print('[Solid]: Inspect and Traceback: OK')

from base import logger
print('[Solid]: Logger: OK')

from base import skeleton_device, skeleton_application
print('[Solid]: Skeletons: OK')


class ImplementorNotFound(Exception):
    pass


def get_implementer():
    try:
        _spec = util.spec_from_file_location("implementor", settings.skeleton_path)
        _module = util.module_from_spec(_spec)
        _spec.loader.exec_module(_module)

        for _name, _obj in inspect.getmembers(_module):
            try:
                if inspect.isclass(_obj) and issubclass(_obj, (
                        skeleton_device.SkeletonDevice,
                        skeleton_application.SkeletonApplication)):
                    logger.debug("Implementation class found: {}".format(_obj))
                    return _obj()
            except TypeError:
                continue

        raise ImplementorNotFound

    except Exception:
        logger.critical("Failed to find Skeleton implementer class {}, check for missing abstract methods".format(traceback.format_exc(limit=5)))
        os._exit(1)


implementer = get_implementer()
