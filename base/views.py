import os
from base import auth
import logging
import concurrent
import time
import threading
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

max_tasks = 5
min_wait_secs = 0.5


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

            self.implementer = get_implementer()
            self.implementer.queue = queue_pub

            webhook = Webhook(queue=queue_pub, implementer=self.implementer)

            mqtt = MqttConnector(implementer=self.implementer, queue=queue_sub, queue_pub=queue_pub)
            mqtt.mqtt_config()
            mqtt.set_on_connect_callback(webhook.webhook_registration)

            router = Router(webhook)
            router.route_setup(app)

            worker_process = mp.Process(target=self.worker_sub, args=(mqtt,), name="onMessage")
            worker_process.start()

            publisher_thread = threading.Thread(target=self.worker_pub, args=(mqtt,), name='Publish', daemon=True)
            publisher_thread.start()

            mqtt.mqtt_client.loop_start()

    def worker_sub(self, mqtt_instance):
        logger.notice('New Queue Sub')
        asyncio.set_event_loop(loop)

        tasks = []
        last = time.time()

        while True:
            time_diff = time.time() - last

            try:
                if len(tasks) > max_tasks or (time_diff >= min_wait_secs and len(tasks) > 0):
                    # send tasks if there's more than 2 seconds waiting
                    loop.run_until_complete(self.send_callback(tasks))
                    tasks = []
                    last = time.time()

                item = queue_sub.get(timeout=10)

                if item:
                    logger.info('New on_message')
                    implementor_type = item['type']

                    if implementor_type == 'device':
                        tasks.append((mqtt_instance.on_message_manager, (item['topic'], item['payload'])))
                    else:
                        tasks.append((mqtt_instance.on_message_application, (item['topic'], item['payload'])))

            except:
                pass

    def worker_pub(self, mqtt_instance):
        logger.notice('New Queue Pub')
        asyncio.set_event_loop(loop)

        while True:
            try:
                item = queue_pub.get(timeout=10)
                if item:
                    logger.info('New publisher')
                    loop.run_until_complete(self.send_task( (mqtt_instance.publisher, (item['io'], item['data'], item['case']) ) ))
            except:
                pass

    async def send_task(self, task):
        logger.info('Running task')
        with concurrent.futures.ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, task[0], *task[1])


    async def send_callback(self, tasks):
        logger.info('Running {} tasks'.format(len(tasks)))
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                loop.run_in_executor(
                    executor,
                    callback,
                    *args
                ) for callback, args in tasks
            ]
