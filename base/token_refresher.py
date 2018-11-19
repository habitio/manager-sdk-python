import concurrent

from base.redis_db import db
from base.settings import settings
from base.utils import rate_limited
from base.constants import DEFAULT_REFRESH_INTERVAL, DEFAULT_RATE_LIMIT, DEFAULT_THREAD_MAX_WORKERS, DEFAULT_REFRESH_MARGIN
import asyncio
import requests
import threading
import datetime
import logging
import time
import traceback

logger = logging.getLogger(__name__)

class TokenRefresherManager(object):

    def __init__(self):
        self.interval = settings.config_refresh.get('interval', DEFAULT_REFRESH_INTERVAL)  # default 60 sec.
        self.client_id = settings.client_id
        self.loop = asyncio.new_event_loop()

    def start(self):
        """
        If refreshing token is enabled in config file, retrieves conf for refresh in implementor
        :return:
        """
        try:
            from base.solid import implementer
            if settings.config_refresh.get('enabled') == True:
                logger.info('**** starting token refresher ****')
                t = threading.Thread(target=self.worker, args=[implementer.get_refresh_token_conf()], name="TokenRefresh")
                t.start()
            else:
                logger.info('**** token refresher is not enabled ****')
        except NotImplementedError as e:
            logger.error("NotImplementedError: {}".format(e))
        except Exception as e:
            logger.alert("Unexpected exception: {} {}".format(e, traceback.format_exc(limit=5)))

    def worker(self, conf_data):
        asyncio.set_event_loop(self.loop)
        loop = asyncio.get_event_loop()

        while True:
            logger.info('new refresh process {}'.format(datetime.datetime.now()))
            loop.run_until_complete(self.make_requests(conf_data))
            time.sleep(self.interval)

    def get_credential_list(self):
        credentials_list = db.full_query('credential-owners/*/channels/*')
        return credentials_list

    async def make_requests(self, conf_data: dict):
        logger.info("{} starting {}".format(threading.currentThread().getName(),  datetime.datetime.now()))

        url = conf_data['url']
        method = conf_data['method']

        loop = asyncio.get_event_loop()

        with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_THREAD_MAX_WORKERS) as executor:
            futures = [
                loop.run_in_executor(
                    executor,
                    self.send_request,
                    credentials, method, url
                )
                for credentials in db.get_credential_list()
            ]
            for response in await asyncio.gather(*futures):
                logger.info(response)

        logger.info("{} finishing {}".format(threading.currentThread().getName(),  datetime.datetime.now()))


    @rate_limited(settings.config_refresh.get('rate_limit', DEFAULT_RATE_LIMIT))
    def send_request(self, credentials_dict, method, url):
        try:
            key = credentials_dict['key']  # credential-owners/[owner_id]/channels/[channel_id]
            channel_id = key.split('/')[-1]
            owner_id = key.split('/')[1]
            credentials = credentials_dict['value']
            client_app_id = credentials['client_id']

            # Validate if token is valid before the request
            now = int(time.time())
            token_expiration_date = credentials['expiration_date']
            if now >= (token_expiration_date - settings.config_refresh.get('token_refresh_interval', DEFAULT_REFRESH_MARGIN)):
                logger.info("Refreshing token {}".format(channel_id))

                manufacturer_client_id = settings.config_manufacturer['credentials'][client_app_id].get('app_id')
                manufacturer_client_secret = settings.config_manufacturer['credentials'][client_app_id].get('app_secret')

                params = {
                    'grant_type': 'refresh_token',
                    'refresh_token': credentials['refresh_token'],
                    'client_id': manufacturer_client_id,
                    'client_secret': manufacturer_client_secret
                }

                response = requests.request(method,  url, params=params)
                if response.status_code == requests.codes.ok:
                    db.set_credentials(response.json(), self.client_id, owner_id, channel_id)
                    return {
                        'response': response.json(),
                        'channel_id': channel_id,
                        'credentials': credentials
                    }
                else:
                    logger.warning('Error in refresh token request {} {}'.format(channel_id, response.json()))
        except Exception:
            logger.error('Unexpected error on send_request for refresh token, {}'.format(traceback.format_exc(limit=5)))

try:
    poll = TokenRefresherManager()
except Exception as e:
    logger.error("Failed start TokenRefresher manager, {} {}".format(e, traceback.format_exc(limit=5)))
