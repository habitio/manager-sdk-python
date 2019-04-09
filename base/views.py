from base import auth
import logging
import concurrent

from base import settings
from base.mqtt_connector import MqttConnector
from base.skeleton import Webhook, Router
from base.solid import get_implementer
import asyncio
import multiprocessing as mp

logger = logging.getLogger(__name__)

loop = asyncio.get_event_loop()

queue_sub = mp.Queue()
queue_pub = mp.Queue()


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
            implementer.queue = queue_pub

            mqtt = MqttConnector(implementer=implementer, queue=queue_sub, queue_pub=queue_pub)

            webhook = Webhook(queue=queue_pub, implementer=implementer)
            router = Router(webhook)
            router.route_setup(app)

            mqtt.mqtt_config()
            mqtt.set_on_connect_callback(webhook.webhook_registration)

            proc = mp.Process(target=self.worker_sub, args=[queue_sub, mqtt], name="onMessage")
            proc.start()

            proc2 = mp.Process(target=self.worker_pub, args=[queue_pub, mqtt], name="Publish")
            proc2.start()

            mqtt.mqtt_client.loop_start()

    def worker_sub(self, queue, mqtt):
        logger.notice('New Queue Sub')
        asyncio.set_event_loop(loop)
        mqtt.mqtt_config()

        while True:
            try:
                item = queue.get()
                if item:
                    logger.info('New on_message')
                    implementor_type = item['type']

                    if implementor_type == 'device':
                        loop.run_until_complete(self.send_task( (mqtt.on_message_manager, (item['topic'], item['payload']) ) ))
                    else:
                        loop.run_until_complete(self.send_task( (mqtt.on_message_application, (item['topic'], item['payload']) ) ))
            except:
                pass

    def worker_pub(self, queue, mqtt):
        logger.notice('New Queue Pub')
        asyncio.set_event_loop(loop)
        mqtt.mqtt_config()

        while True:
            try:
                item = queue.get()
                if item:
                    logger.info('New publisher')
                    loop.run_until_complete(self.send_task( (mqtt.publisher, (item['io'], item['data'], item['case']) ) ))
            except:
                pass

    async def send_task(self, task):
        logger.info('Running task')
        with concurrent.futures.ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, task[0], *task[1])
