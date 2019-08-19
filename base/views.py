from base import auth
import threading
import concurrent
from base import settings, logger
from base.constants import DEFAULT_MIN_TIMEOUT, DEFAULT_MAX_TIMEOUT
from base.mqtt_connector import MqttConnector
from base.skeleton import Webhook, Router
from base.solid import get_implementer
import asyncio
import multiprocessing as mp
from queue import Empty
from asgiref.sync import sync_to_async
from base.exceptions import InvalidUsage, handle_invalid_usage

max_tasks = mp.cpu_count() - 1
min_timeout = settings.config_mqtt.get("min_timeout_secs", DEFAULT_MIN_TIMEOUT)
max_timeout = settings.config_mqtt.get("max_timeout_secs", DEFAULT_MAX_TIMEOUT)
loop_sub = asyncio.new_event_loop()
asyncio.set_event_loop(loop_sub)

queue_timeout = min_timeout

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
        app.register_error_handler(InvalidUsage, handle_invalid_usage)
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

            for _ in range(max_tasks):
                worker_thread = mp.Process(target=worker_sub, args=(mqtt,), name=f"onMessage_{_}")
                worker_thread.start()

            publisher_thread = threading.Thread(target=worker_pub, args=(mqtt,), name='Publish', daemon=True)
            publisher_thread.start()

            mqtt.mqtt_client.loop_start()


async def _get_item(queue):
    item = None
    global queue_timeout
    try:
        item = queue.get(timeout=queue_timeout)
        queue_timeout = min_timeout
    except Empty:
        queue_timeout = max_timeout
    except Exception as e:
        logger.error('Error on get_item: {}\nQueue: {}'.format(e, queue))
    return item


async def _get_sub_task(item, mqtt_instance):
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


async def _send_callback(mqtt_instance, queue):
    item = await _get_item(queue)
    task = await _get_sub_task(item, mqtt_instance)
    await _deal_with_task(task)


async def _worker_sub_process(mqtt_instance, queue_sub_):
    await _send_callback(mqtt_instance, queue_sub_)
    asyncio.ensure_future(_worker_sub_process(mqtt_instance, queue_sub_))
    mp.current_process().is_alive()


def worker_sub(mqtt_instance):
    logger.notice('New Queue Sub')
    asyncio.set_event_loop(loop_sub)

    try:
        asyncio.ensure_future(_worker_sub_process(mqtt_instance, queue_sub))
        loop_sub.run_forever()
    finally:
        loop_sub.run_until_complete(loop_sub.shutdown_asyncgens())
        loop_sub.close()


def worker_pub(mqtt_instance):
    logger.notice('New Queue Pub')
    loop_pub = asyncio.new_event_loop()
    asyncio.set_event_loop(loop_pub)
    global queue_timeout

    while True:
        try:
            item = queue_pub.get(timeout=queue_timeout)
            queue_timeout = min_timeout
            if item:
                logger.info('New publisher')
                loop_pub.run_until_complete(send_task(
                    (mqtt_instance.publisher, (item['io'], item['data'], item['case'])), loop_pub
                ))
        except Empty:
            queue_timeout = max_timeout
        except Exception:
            pass


async def send_task(task, loop):
    logger.info('Running task')
    with concurrent.futures.ThreadPoolExecutor() as executor:
        await loop.run_in_executor(executor, task[0], *task[1])
