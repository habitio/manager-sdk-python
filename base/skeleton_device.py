from .skeleton_base import SkeletonBase
from .constants import DEFAULT_BEFORE_EXPIRES

class SkeletonDevice(SkeletonBase):

    def __init__(self):
        super(SkeletonDevice, self).__init__()
        self._type = 'device'
        self.DEFAULT_BEFORE_EXPIRES = DEFAULT_BEFORE_EXPIRES

SkeletonBase.register(SkeletonDevice)
