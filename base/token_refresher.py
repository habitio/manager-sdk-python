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
        self.interval = settings.config_refresh.get('interval_seconds', DEFAULT_REFRESH_INTERVAL)  # default 60 sec.
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
                for credentials in self.get_credential_list()
            ]
            for response in await asyncio.gather(*futures):
                if response: logger.info(response)

        logger.info("{} finishing {}".format(threading.currentThread().getName(),  datetime.datetime.now()))

    def get_new_expiration_date(self, credentials):
        now = int(time.time())
        token_refresh_interval = settings.config_refresh.get('before_expires_seconds', DEFAULT_BEFORE_EXPIRES)
        expires_in = int(credentials['expires_in']) - token_refresh_interval
        expiration_date = now + expires_in
        credentials['expiration_date'] = expiration_date

        return credentials

    @rate_limited(settings.config_refresh.get('rate_limit', DEFAULT_RATE_LIMIT))
    def send_request(self, credentials_dict, method, url):
        try:
            key = credentials_dict['key']  # credential-owners/[owner_id]/channels/[channel_id]
            channel_id = key.split('/')[-1]
            owner_id = key.split('/')[1]
            credentials = credentials_dict['value']
            try:
                client_app_id = credentials['client_id']
            except KeyError:
                logger.debug('Missing client_id for {}'.format(key))
                return

            # Validate if token is valid before the request
            try:
                now = int(time.time())
                token_expiration_date = credentials['expiration_date']
            except KeyError:
                logger.debug('Missing expiration_date for {}'.format(key))
                return

            if now >= (token_expiration_date - settings.config_refresh.get('token_refresh_interval', DEFAULT_REFRESH_MARGIN)):
                logger.info("Refreshing token {}".format(key))
                try:
                    manufacturer_client_id = settings.config_manufacturer['credentials'][client_app_id].get('app_id')
                except KeyError:
                    logger.debug('Credentials not found for for {}'.format(client_app_id))
                    return

                params = {
                    'grant_type': 'refresh_token',
                    'refresh_token': credentials['refresh_token'],
                    'client_id': manufacturer_client_id
                }

                response = requests.request(method,  url, params=params)
                if response.status_code == requests.codes.ok:
                    new_credentials = self.get_new_expiration_date(response.json())
                    logger.debug('new credentials {}'.format(key))
                    db.set_credentials(new_credentials, client_app_id, owner_id, channel_id)
                    return new_credentials
                else:
                    logger.warning('Error in refresh token request {} {}'.format(channel_id, response.text))
            else:
                logger.debug("access token hasn't expired yet {}".format(key))
        except Exception:
            logger.error('Unexpected error on send_request for refresh token, {}'.format(traceback.format_exc(limit=5)))

try:
    refresher = TokenRefresherManager()
except Exception as e:
    logger.error("Failed start TokenRefresher manager, {} {}".format(e, traceback.format_exc(limit=5)))
