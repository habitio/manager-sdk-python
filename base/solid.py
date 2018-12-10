print('[Solid]: Settings: Setting up')
from base.settings import settings
print('[Solid]: Settings: OK')

print('[Solid]: Skeleton: Setting up')
from base import skeleton_device
print('[Solid]: Skeleton: OK')

print('[Solid]: ImportLib::Utils: Setting up')
from importlib import util
print('[Solid]: ImportLib::Utils: OK')

print('[Solid]: Inspect and Logging: Setting up')
import inspect, logging, traceback
print('[Solid]: Inspect and Logging: OK')

logger = logging.getLogger(__name__)


def get_implementer():
    try:
        _spec = util.spec_from_file_location("implementor", settings.skeleton_path)

        _module = util.module_from_spec(_spec)
        logger.trace('Module: {}'.format(_module))

        _spec.loader.exec_module(_module)
        logger.trace('Spec: {}'.format(_spec))

        for _name, _obj in inspect.getmembers(_module):
            try:
                logger.trace('-------------------------------')
                logger.trace('Item: {} - {}'.format(_name, _obj))
                logger.trace('Is class? {}'.format(inspect.isclass(_obj)))
                logger.trace('Is subclass from Skeleton? {}'.format(issubclass(_obj, (skeleton_device.SkeletonDevice,))))

                if inspect.isclass(_obj) and issubclass(_obj, skeleton_device.SkeletonDevice,):
                    logger.debug("Implementation class found: {}".format(_obj))
                    return _obj()
            except TypeError:
                continue

        logger.critical("Failed to find Skeleton implementer class")

    except Exception:

        logger.critical("Failed to find Skeleton implementer class {}".format(traceback.format_exc(limit=5)))
        exit()


implementer = get_implementer()
