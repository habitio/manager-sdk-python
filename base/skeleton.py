from base.settings import settings

if settings.implementor_type == 'device':
    from base import skeleton_device
    Skeleton = skeleton_device.SkeletonDevice
    Router  = skeleton_device.router.RouterDevice
    Webhook = skeleton_device.webhook.WebhookHubDevice
elif settings.implementor_type == 'application':
    from base import skeleton_application
    Skeleton = skeleton_application.SkeletonApplication
    Router = skeleton_application.router.RouterApplication
    Webhook = skeleton_application.webhook.WebhookHubApplication
elif settings.implementor_type == 'hardware':
    from base import skeleton_hardware
    Skeleton = skeleton_hardware.SkeletonHardware
    Router = skeleton_hardware.router.RouterHardware
    Webhook = skeleton_hardware.webhook.WebhookHubHardware
