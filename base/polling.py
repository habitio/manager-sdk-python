import concurrent

from base.redis_db import db
from base.settings import settings
from base.utils import rate_limited
import asyncio
import requests
import threading
import datetime
import logging
import time
import traceback

logger = logging.getLogger(__name__)

class PollingManager(object):

    def __init__(self):
        self.interval = settings.config_polling.get('interval', 60)  # default 60 sec.
        self.client_id = settings.client_id
        self.loop = asyncio.new_event_loop()

    def start(self):
        """
        If polling is enabled in config file, retrieves conf for polling in implementor
        :return:
        """
        try:
            from base.solid import implementer
            if settings.config_polling.get('enabled') == True:
                logger.info('**** starting polling ****')
                t = threading.Thread(target=self.worker, args=[implementer.get_polling_conf()], name="Polling")
                t.start()
            else:
                logger.info('**** polling is not enabled ****')
        except NotImplementedError as e:
            logger.error("NotImplementedError: {}".format(e))
        except Exception as e:
            logger.alert("Unexpected exception: {} {}".format(e, traceback.format_exc(limit=5)))

    def authorization(self, credentials):
        headers = {
            'Authorization': '{token_type} {access_token}'.format(
                token_type=credentials['token_type'],
                access_token=credentials['access_token']),
            'Content-Type': 'application/json'
        }
        return headers

    def worker(self, conf_data):
        asyncio.set_event_loop(self.loop)
        loop = asyncio.get_event_loop()

        while True:
            logger.info('new polling request {}'.format(datetime.datetime.now()))
            loop.run_until_complete(self.make_requests(conf_data))
            time.sleep(self.interval)

    async def make_requests(self, conf_data: dict):
        logger.info("{} starting {}".format(threading.currentThread().getName(),  datetime.datetime.now()))

        url = conf_data['url']
        method = conf_data['method']
        data = conf_data.get('data')
        params = conf_data.get('params')

        loop = asyncio.get_event_loop()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                loop.run_in_executor(
                    executor,
                    self.send_request,
                    channel_id, method, url, params, data
                )
                for channel_id in db.get_channels()
            ]
            for response in await asyncio.gather(*futures):
                if response: implementer.polling(response)

        logger.info("{} finishing {}".format(threading.currentThread().getName(),  datetime.datetime.now()))

    @rate_limited(settings.config_polling.get('rate_limit', 1))  # 1/sec default ?
    def send_request(self, channel_id, method, url, params, data):
        credentials = db.get_credentials(self.client_id, '*', channel_id)

        # Validate if token is valid before the request
        now = int(time.time())
        token_expiration_date = credentials['expiration_date']
        if now > token_expiration_date:
            logger.info("No polling requested, access token has expired {}".format(channel_id))
            return False

        response = requests.request(method,  url, params=params, data=data, headers=self.authorization(credentials))
        if response.status_code == requests.codes.ok:
            return {
                'response': response.json(),
                'channel_id': channel_id,
                'credentials': credentials
            }

        logger.warning('Error in polling request {} {}'.format(channel_id, response.json()))
        return False

try:
    poll = PollingManager()
except Exception as e:
    logger.error("Failed start polling manager, {} {}".format(e, traceback.format_exc(limit=5)))
