from base import auth
import logging
import concurrent
import time

from base import settings
from base.mqtt_connector import MqttConnector
from base.skeleton import Webhook, Router
from base.solid import get_implementer
import asyncio
import multiprocessing as mp

logger = logging.getLogger(__name__)
loop = asyncio.get_event_loop()

max_tasks = 5

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
            queue = mp.Queue()
            queue_pub = mp.Queue()
            
            implementer = get_implementer()
            implementer.queue = queue_pub

            mqtt = MqttConnector(implementer=implementer, queue=queue, queue_pub=queue_pub)

            webhook = Webhook(queue=queue_pub, implementer=implementer)
            webhook.webhook_registration()
            router = Router(webhook)
            router.route_setup(app)
            mqtt.mqtt_config()

            proc = mp.Process(target=self.worker_sub, args=[queue, mqtt], name="onMessage")
            proc.start()

            proc2 = mp.Process(target=self.worker_pub, args=[queue_pub, mqtt], name="Publish")
            proc2.start()

            mqtt.start()

    def worker_sub(self, queue, mqtt):
        logger.notice('New Queue Sub')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mqtt.mqtt_config()

        while True:
            try:
                item = queue.get_nowait()
                implementor_type = item['type']

                if implementor_type == 'device':
                    loop.run_until_complete(self.send_task( (mqtt.on_message_manager, (item['topic'], item['payload']) ) ))
                else:
                    loop.run_until_complete(self.send_task( (mqtt.on_message_manager, (item['topic'], item['payload']) ) ))

            except:
                pass

    def worker_pub(self, queue, mqtt):
        logger.notice('New Queue Pub')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mqtt.mqtt_config()

        while True:
            try:
                item = queue.get_nowait()
                loop.run_until_complete(self.send_task( (mqtt.publisher, (item['io'], item['data'], item['case']) ) ))
            except:
                pass

    async def send_task(self, task):
        logger.info('Running task')
        with concurrent.futures.ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, task[0], *task[1])
