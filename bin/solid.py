from bin.settings import settings
from bin import skeleton
from importlib import util
import inspect,logging

logger = logging.getLogger(__name__)

try:
    spec = util.spec_from_file_location("implementor",settings.skeleton_path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj):
            if inspect.isabstract(obj) != True:
                if issubclass(obj,skeleton.Skeleton):
                    Solid = obj
except Exception as ex:
    logger.critical("Failed to find Skeleton implementer class")
    logger.trace(ex)
    exit()
