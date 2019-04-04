from base import auth
import logging

from base import settings
from base.mqtt_connector import MqttConnector
from base.skeleton import Webhook, Router
from base.solid import get_implementer


logger = logging.getLogger(__name__)

class Views:

    def __init__(self, _app=None):
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

            if not settings.mqtt:  # means also have to run webserver
                webhook = Webhook(mqtt=mqtt, implementer=implementer)
                webhook.webhook_registration()
                router = Router(webhook)
                router.route_setup(app)
                mqtt.start()
            else:
                mqtt.mqtt_config()
