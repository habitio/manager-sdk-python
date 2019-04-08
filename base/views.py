from base import auth
import logging
import concurrent
import time

from base import settings
from base.mqtt_connector import MqttConnector
from base.mqtt_aclient import MqttConnector as MqttAConnector
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
            mqtta = MqttAConnector()

            loop.run_until_complete(mqtta.start_connection())
            
            implementer = get_implementer()
            implementer.mqtt = mqtta

            queue = mp.Queue()
            queue_pub = mp.Queue()

            mqtt = MqttConnector(implementer=implementer, queue=queue, queue_pub=queue_pub)

            if not settings.mqtt:  # means also have to run webserver
                webhook = Webhook(mqtt=mqtt, implementer=implementer)
                webhook.webhook_registration()
                router = Router(webhook)
                router.route_setup(app)
                mqtt.mqtt_config()

                proc = mp.Process(target=self.worker_sub, args=[queue, mqtt], name="onMessage") 
                proc.start()
                
                proc2 = mp.Process(target=self.worker_pub, args=[queue_pub, mqtt], name="Publish") 
                proc2.start()
                
                mqtt.mqtt_client.loop_forever()

            else:
                mqtt.mqtt_config()

    def worker_sub(self, queue, mqtt):
        logger.notice('New Queue Sub {} {} {}'.format(mqtt.mqtt_client._username, mqtt.mqtt_client._password, mqtt.mqtt_client._ssl))
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mqtt.mqtt_config()

        tasks = []
        last = int(time.time())
        
        while True:
            if len(tasks) > max_tasks or last - int(time.time()) >=2 and len(tasks) > 0:
                loop.run_until_complete(self.send_callback(tasks))
                tasks = []    
            try:
                item = queue.get_nowait()
                implementor_type = item['type']

                if implementor_type == 'device':
                    tasks.append((mqtt.on_message_manager, (item['topic'], item['payload'])))
                else:
                    tasks.append((mqtt.on_message_application, (item['topic'], item['payload'])))
            except:
                pass

    def worker_pub(self, queue, mqtt):
        logger.notice('New Queue Pub {} {} {}'.format(mqtt.mqtt_client._username, mqtt.mqtt_client._password, mqtt.mqtt_client._ssl))
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mqtt.mqtt_config()

        tasks = []
        last = int(time.time())

        while True:
            if len(tasks) > max_tasks or last - int(time.time()) >=2 and len(tasks) > 0:
                loop.run_until_complete(self.send_callback(tasks))
                tasks = []
            try:
                item = queue.get_nowait()
                tasks.append((mqtt.publisher, (item['io'], item['data'], item['case'])))
            except:
                pass

    async def send_callback(self, tasks):
        logger.info('Running {}'.format(tasks))
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                loop.run_in_executor(
                    executor,
                    callback,
                    *args
                ) for callback, args in tasks
            ]

            for response in await asyncio.gather(**futures):
                if response: logger.info(response)


