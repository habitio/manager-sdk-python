from base.settings import settings
from base import skeleton
from importlib import util
import inspect,logging

logger = logging.getLogger(__name__)

def get_implementer():
    try:
        spec = util.spec_from_file_location("implementor",settings.skeleton_path)
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)

        print("ONly once")
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj):
                if inspect.isabstract(obj) != True:
                    if issubclass(obj,skeleton.Skeleton):
                        logger.debug("Implementation class found: {}".format(obj))
                        return obj()
        logger.critical("Failed to find Skeleton implementer class")
    except Exception as ex:
        logger.critical("Failed to find Skeleton implementer class")
        logger.trace(ex)
        exit()

implementer = get_implementer()
