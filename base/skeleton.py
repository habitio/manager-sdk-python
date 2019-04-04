from base import settings

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
