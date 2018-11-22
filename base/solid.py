import inspect
import logging
import traceback
from importlib import util

from base import skeleton
from base.settings import settings

logger = logging.getLogger(__name__)


def get_implementer():
    try:
        spec = util.spec_from_file_location("implementor", settings.skeleton_path)
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj):
                if inspect.isabstract(obj) != True:
                    if issubclass(obj, skeleton.Skeleton):
                        logger.debug("Implementation class found: {}".format(obj))
                        return obj()
        logger.critical("Failed to find Skeleton implementer class")
    except Exception as e:
        logger.critical("Failed to find Skeleton implementer class {}".format(traceback.format_exc(limit=5)))
        exit()


implementer = get_implementer()
