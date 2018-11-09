from base.redis_db import db
from base.settings import settings
import asyncio
import requests 
import threading
import datetime
import logging

logger = logging.getLogger(__name__)

class PollingManager(object):

    def __init__(self):
        self.interval = settings.config_polling.get('interval')
        self.client_id = settings.client_id
        self.loop = asyncio.new_event_loop()
        #self.queue = Queue()

    def get_channels(self):
        channels = db.get_channels()
        return channels

    def authorization(self, credentials):
        headers = {
            'Authorization': '{token_type} {access_token}'.format(
                token_type=credentials['token_type'],
                access_token=credentials['access_token']),
            'Content-Type': 'application/json'
        }
        return headers

    async def make_request(self, channel_id: str, url: str):
        credentials = db.get_credentials(self.client_id, '*', channel_id)
        logger.info("{} starting {} {}".format(threading.currentThread().getName(), channel_id,  datetime.datetime.now()))
        response = requests.get(url, headers=self.authorization(credentials))
        logger.info("{} finishing {} {}".format(threading.currentThread().getName(), channel_id,  datetime.datetime.now()))
        return {
            'response': response,
            'channel_id': channel_id
        }


    def process_result(self, future):
        print(future.result())

    def worker(self, url):
        asyncio.set_event_loop(self.loop)
        loop = asyncio.get_event_loop()

        for channel_id in self.get_channels():
            task = loop.create_task(self.make_request(channel_id, url))
            task.add_done_callback(self.process_result)

        loop.run_forever()

