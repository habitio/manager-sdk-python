from base.settings import settings
from base import skeleton_device, skeleton_application

if settings.implementor_type == 'device':
    Skeleton = skeleton_device.SkeletonDevice
elif settings.implementor_type == 'application':
    Skeleton = skeleton_application.SkeletonApplication
