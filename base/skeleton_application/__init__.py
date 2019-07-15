from base.common.skeleton_base import SkeletonBase
from .router import *
from .webhook import *


class SkeletonApplication(SkeletonBase):
    pass


SkeletonBase.register(SkeletonApplication)
