from base import auth
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
            loop = asyncio.new_event_loop()

            self.implementer = get_implementer()
            self.implementer.queue = queue_pub

            webhook = Webhook(queue=queue_pub, implementer=self.implementer)
            webhook.patch_endpoints()

            mqtt = MqttConnector(implementer=self.implementer, queue=queue_sub, queue_pub=queue_pub)
            mqtt.mqtt_config()
            mqtt.set_on_connect_callback(webhook.webhook_registration)

            router = Router(webhook)
            router.route_setup(app)

            worker_thread = threading.Thread(target=workers, args=(mqtt, loop), name="messages", daemon=True)
            worker_thread.start()

            mqtt.mqtt_client.loop_start()


async def _get_item(queue):
    item = None
    try:
        item = queue.get(timeout=min_timeout)
    except Empty:
        pass
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


async def _get_pub_task(item, mqtt_instance):
    task = None
    if item:
        logger.info('New on_message')
        task = (mqtt_instance.publisher, (item['io'], item['data'], item['case']))
        logger.info(f'Processed Task: {task}')
    return task


@sync_to_async
def _deal_with_task(task):
    if task:
        task[0](*task[1])
        logger.info(f'Executed Task: {task}')


async def _send_callback(mqtt_instance, queue):
    item = await _get_item(queue)
    if queue == queue_sub:
        task = await _get_sub_task(item, mqtt_instance)
    else:
        task = await _get_pub_task(item, mqtt_instance)
    await _deal_with_task(task)


async def _worker_sub_process(mqtt_instance, queue_sub_):
    try:
        async with sem:
            asyncio.ensure_future(_worker_sub_process(mqtt_instance, queue_sub_))
            await _send_callback(mqtt_instance, queue_sub_)
    except RuntimeError:
        pass
    except Exception as e:
        logger.error('Error on worker_sub_process: {}'.format(e))
    finally:
        asyncio.ensure_future(_worker_sub_process(mqtt_instance, queue_sub_))


def worker_sub(mqtt_instance, loop_sub):
    logger.notice('New Queue Sub')
    asyncio.set_event_loop(loop_sub)

    try:
        asyncio.ensure_future(_worker_sub_process(mqtt_instance, queue_sub))
        loop_sub.run_forever()
    finally:
        loop_sub.run_until_complete(loop_sub.shutdown_asyncgens())
        loop_sub.close()


async def _worker_pub_process(mqtt_instance, queue_pub_):
    try:
        async with sem:
            asyncio.ensure_future(_worker_pub_process(mqtt_instance, queue_pub_))
            await _send_callback(mqtt_instance, queue_pub_)
    except RuntimeError:
        pass
    except Exception as e:
        logger.error('Error on worker_pub_process: {}'.format(e))
    finally:
        asyncio.ensure_future(_worker_pub_process(mqtt_instance, queue_pub_))


def workers(mqtt_instance, loop_):
    asyncio.set_event_loop(loop_)

    try:
        asyncio.ensure_future(_worker_pub_process(mqtt_instance, queue_pub))
        asyncio.ensure_future(_worker_sub_process(mqtt_instance, queue_sub))
        loop_.run_forever()
    finally:
        loop_.run_until_complete(loop_.shutdown_asyncgens())
        loop_.close()
