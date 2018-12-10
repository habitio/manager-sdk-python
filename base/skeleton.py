from base.settings import settings
from base import skeleton_device, skeleton_application

if settings.skeleton_type == 'device':
    Skeleton = skeleton_device.SkeletonDevice
elif settings.skeleton_type == 'application':
    Skeleton = skeleton_application.SkeletonApplication
