import concurrent

from base.redis_db import db
from base.settings import settings
import asyncio
import requests
import threading
import datetime
import logging
import time

logger = logging.getLogger(__name__)

class PollingManager(object):

    def __init__(self):
        self.interval = settings.config_polling.get('interval')
        self.client_id = settings.client_id
        self.loop = asyncio.new_event_loop()

    def authorization(self, credentials):
        headers = {
            'Authorization': '{token_type} {access_token}'.format(
                token_type=credentials['token_type'],
                access_token=credentials['access_token']),
            'Content-Type': 'application/json'
        }
        return headers

    def send_request(self, channel_id, method, url, params, data):
        credentials = db.get_credentials(self.client_id, '*', channel_id)
        s = requests.Session()
        req = requests.Request(method,  url, params=params, data=data, headers=self.authorization(credentials))
        prep = s.prepare_request(req)
        response = s.send(prep)

        if response.status_code == requests.codes.ok:
            return {
                'response': response.json(),
                'channel_id': channel_id,
                'credentials': credentials
            }
        else:
            logger.warning('Error in polling request: {}'.format(response.json()))

    async def make_requests(self, conf_data: dict):
        logger.info("{} starting {}".format(threading.currentThread().getName(),  datetime.datetime.now()))
        from base.solid import implementer

        url = conf_data['url']
        method = conf_data['method']
        data = conf_data.get('data')
        params = conf_data.get('params')

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            futures = [
                loop.run_in_executor(
                    executor,
                    self.send_request,
                    channel_id, method, url, params, data
                )
                for channel_id in db.get_channels()
            ]
            for response in await asyncio.gather(*futures):
                # send response to webhook ?
                if response: implementer.polling(response)

        logger.info("{} finishing {}".format(threading.currentThread().getName(),  datetime.datetime.now()))


    def worker(self, conf_data):
        asyncio.set_event_loop(self.loop)
        loop = asyncio.get_event_loop()

        while True:
            logger.info('new polling request {}'.format(datetime.datetime.now()))
            loop.run_until_complete(self.make_requests(conf_data))
            time.sleep(self.interval)
