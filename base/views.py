from base import auth
from base import logger

from base import settings
from base.mqtt_connector import MqttConnector
from base.skeleton import Webhook, Router
from base.solid import get_implementer

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
            implementer = get_implementer()

            mqtt = MqttConnector(implementer=implementer)
            webhook = Webhook(mqtt=mqtt, implementer=implementer)
            router = Router(webhook)
            router.route_setup(app)


            mqtt.set_on_connect_callback(webhook.webhook_registration)
            mqtt.mqtt_config()
