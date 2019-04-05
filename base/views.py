from base import auth
import logging

from base import settings
from base.mqtt_connector import MqttConnector
from base.mqtt_aclient import MqttConnector as MqttAConnector
from base.skeleton import Webhook, Router
from base.solid import get_implementer
import asyncio

logger = logging.getLogger(__name__)
loop = asyncio.get_event_loop()

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
            mqtta = MqttAConnector()

            loop.run_until_complete(mqtta.start_connection())
            
            implementer = get_implementer()
            implementer.mqtt = mqtta

            mqtt = MqttConnector(implementer=implementer)

            if not settings.mqtt:  # means also have to run webserver
                webhook = Webhook(mqtt=mqtt, implementer=implementer)
                webhook.webhook_registration()
                router = Router(webhook)
                router.route_setup(app)
                mqtt.start()
            else:
                mqtt.mqtt_config()
