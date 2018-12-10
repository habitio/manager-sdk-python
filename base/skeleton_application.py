from .skeleton_base import SkeletonBase


class SkeletonApplication(SkeletonBase):

    def __init__(self):
        super(SkeletonApplication, self).__init__()
        self._type = 'application'

SkeletonBase.register(SkeletonApplication)
