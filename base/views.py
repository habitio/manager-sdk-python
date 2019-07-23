from base import auth
import concurrent
import threading
from base import settings, logger
from base.constants import DEFAULT_MAX_MQTT_TASKS, DEFAULT_MIN_TIMEOUT, DEFAULT_MAX_TIMEOUT
from base.mqtt_connector import MqttConnector
from base.skeleton import Webhook, Router
from base.solid import get_implementer
import asyncio
import multiprocessing as mp
from queue import Empty
from asgiref.sync import sync_to_async

max_tasks = settings.config_mqtt.get("max_tasks", DEFAULT_MAX_MQTT_TASKS)
min_timeout = settings.config_mqtt.get("min_timeout_secs", DEFAULT_MIN_TIMEOUT)
max_timeout = settings.config_mqtt.get("max_timeout_secs", DEFAULT_MAX_TIMEOUT)

loop = asyncio.get_event_loop()
sem = asyncio.Semaphore(max_tasks)

queue_sub = mp.Queue()
queue_pub = mp.Queue()


class Views:

    def __init__(self, _app=None):
        self._timeout = max_timeout
        self.kickoff(_app)

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        self._timeout = value

    def kickoff(self, app):
        """
        Setting up manager before it starts serving

        """
        logger.verbose("Starting sdk with a kickoff ...")
        auth.get_access()

        if settings.block["access_token"] != "":

            self.implementer = get_implementer()
            self.implementer.queue = queue_pub

            webhook = Webhook(queue=queue_pub, implementer=self.implementer)
            webhook.patch_endpoints()

            mqtt = MqttConnector(implementer=self.implementer, queue=queue_sub, queue_pub=queue_pub)
            mqtt.mqtt_config()
            mqtt.set_on_connect_callback(webhook.webhook_registration)

            router = Router(webhook)
            router.route_setup(app)

            worker_thread = threading.Thread(target=worker_sub, args=(mqtt,), name="onMessage", daemon=True)
            worker_thread.start()

            publisher_thread = threading.Thread(target=worker_pub, args=(mqtt,), name='Publish', daemon=True)
            publisher_thread.start()

            mqtt.mqtt_client.loop_start()


async def _get_item():
    item = None
    try:
        item = queue_sub.get(timeout=min_timeout)
    except Empty:
        pass
    except Exception as e:
        logger.error('Error on get_item: {}'.format(e))
    return item


async def _get_task(item, mqtt_instance):
    task = None
    if item:
        logger.info('New on_message')
        implementor_type = item['type']

        if implementor_type == 'device':
            task = (mqtt_instance.on_message_manager, (item['topic'], item['payload']))
        else:
            task = (mqtt_instance.on_message_application, (item['topic'], item['payload']))
        logger.info(f'Processed Task: {task}')
    return task


@sync_to_async
def _deal_with_task(task):
    if task:
        task[0](*task[1])
        logger.info(f'Executed Task: {task}')


async def _send_callback(mqtt_instance):
    item = await _get_item()
    task = await _get_task(item, mqtt_instance)
    await _deal_with_task(task)


async def _worker_sub_process(mqtt_instance):
    async with sem:
        asyncio.ensure_future(_worker_sub_process(mqtt_instance), loop=loop)
        await _send_callback(mqtt_instance)


def worker_sub(mqtt_instance):
    logger.notice('New Queue Sub')
    asyncio.set_event_loop(loop)

    try:
        asyncio.ensure_future(_worker_sub_process(mqtt_instance))
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


def worker_pub(mqtt_instance):
    logger.notice('New Queue Pub')
    asyncio.set_event_loop(loop)

    timeout_pub = max_timeout

    while True:
        try:
            item = queue_pub.get(timeout=timeout_pub)
            if item:
                timeout_pub = min_timeout
                logger.info('New publisher')
                loop.run_until_complete(send_task(
                    (mqtt_instance.publisher, (item['io'], item['data'], item['case']))
                ))
        except Empty:
            timeout_pub = max_timeout
            pass
        except:
            pass


async def send_task(task):
    logger.info('Running task')
    with concurrent.futures.ThreadPoolExecutor() as executor:
        await loop.run_in_executor(executor, task[0], *task[1])
