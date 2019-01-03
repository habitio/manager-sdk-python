from base import auth
from base import logger
from base.mqtt_connector import mqtt
from base.settings import settings
from base.utils import format_str
from base.skeleton import Webhook, Router


class Views:

    def __init__(self, _app):
        self.kickoff(_app)

    def kickoff(self, app):
        '''
        Setting up manager before it starts serving

        '''
        logger.verbose("Starting sdk with a kickoff ...")
        auth.get_access()
        if settings.block["access_token"] != "":
            webhook = Webhook()
            router = Router(webhook)
            router.route_setup(app)

            mqtt.set_on_connect_callback(webhook.webhook_registration)
            mqtt.mqtt_config()

