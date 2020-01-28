import concurrent

from base import settings, logger
from base.redis_db import get_redis
from base.utils import rate_limited
from base.constants import DEFAULT_POLLING_INTERVAL, DEFAULT_RATE_LIMIT, DEFAULT_THREAD_MAX_WORKERS
from multiprocessing.pool import ThreadPool
from itertools import repeat
import asyncio
import requests
import threading
import datetime
import time
import traceback


class PollingManager(object):

    def __init__(self, implementer=None):
        self.interval = settings.config_polling.get('interval_seconds', DEFAULT_POLLING_INTERVAL)  # default 60 sec.
        self.client_id = settings.client_id
        self.loop = asyncio.new_event_loop()
        self.thread = None
        self.db = get_redis()
        self.implementer = implementer
        self.pool_requests = None

    def start(self):
        """
        If polling is enabled in config file, retrieves conf for polling in implementor
        """
        try:
            if settings.config_polling.get('enabled') is True:
                logger.info('[Polling] **** starting polling ****')
                conf_data = self.implementer.get_polling_conf()
                if type(conf_data) is not list:
                    conf_data = [conf_data]
                n_processes = settings.config_polling.get('requests_pool', DEFAULT_THREAD_MAX_WORKERS)
                self.pool_requests = ThreadPool(processes=n_processes)
                self.thread = threading.Thread(target=self.worker, args=[conf_data],
                                               name="Polling")
                self.thread.daemon = True
                self.thread.start()
            else:
                logger.info('[Polling] **** polling is not enabled ****')
        except NotImplementedError as e:
            logger.error("[Polling] NotImplementedError: {}".format(e))
        except Exception:
            logger.alert(f"[Polling] Unexpected exception: {traceback.format_exc(limit=5)}")

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
            logger.info('[Polling] new polling request {}'.format(datetime.datetime.now()))
            try:
                loop.run_until_complete(self.make_requests(conf_data))
            except Exception:
                logger.error(f'[Polling] Error on worker loop, {traceback.format_exc(limit=5)}')
            time.sleep(self.interval)

    async def make_requests(self, conf_data: dict):
        try:
            logger.info(f"[Polling] {threading.currentThread().getName()} starting {datetime.datetime.now()}")

            loop = asyncio.get_event_loop()

            with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_THREAD_MAX_WORKERS) as executor:
                futures = [
                    loop.run_in_executor(
                        executor,
                        self.send_request,
                        conf_data, channel_id
                    )
                    for channel_id in self.db.get_channels()
                ]
                for response in await asyncio.gather(*futures):
                    if response:
                        for resp in response:
                            self.implementer.polling(resp)

            logger.info("[Polling] {} finishing {}".format(threading.currentThread().getName(),
                                                           datetime.datetime.now()))
        except Exception:
            logger.error("[Polling] Error on make_requests: {}".format(traceback.format_exc(limit=5)))

    @rate_limited(settings.config_polling.get('rate_limit', DEFAULT_RATE_LIMIT))
    def send_request(self, conf_data, channel_id):
        try:
            # validate if channel exists
            credentials_list = self.db.full_query('credential-owners/*/channels/{}'.format(channel_id))
            logger.info('[Polling] {} results found for channel_id: {}'.format(len(credentials_list), channel_id))

            for credential_dict in credentials_list:  # try until we find valid credentials
                cred_key = credential_dict['key']
                credentials = credential_dict['value']

                is_valid = self.validate_channel(cred_key)
                if not is_valid:
                    logger.debug('[Polling] Invalid channel {}'.format(cred_key))
                    continue

                # Validate if token is valid before the request
                now = int(time.time())
                token_expiration_date = credentials['expiration_date']
                if now > token_expiration_date and not token_expiration_date == 0:
                    logger.debug("[Polling] access token expired {} - now:{}, expiration:{}".format(
                        cred_key, now, token_expiration_date))
                    continue

                resp_list = []
                results = self.pool_requests.starmap(self.get_response, zip(conf_data, repeat(credentials),
                                                                            repeat(channel_id), repeat(cred_key)))
                resp_list.extend([result for result in results if result])

                if resp_list:
                    return resp_list
        except requests.exceptions.RequestException as e:
            logger.error('Request Error on polling.send_request {}'.format(e))
            return False

        except Exception:
            logger.error(f'[Polling] Unknown error on polling.send_request {traceback.format_exc(limit=5)}')
        logger.notice('[Polling] No valid credentials found for channel {}'.format(channel_id))
        return False

    def validate_channel(self, credential_key):
        try:
            channel_id = credential_key.split('/')[-1]
            owner_id = credential_key.split('/')[1]
            channel_template_id = self.implementer.get_channel_by_owner(owner_id, channel_id)
            return channel_template_id
        except Exception:
            logger.debug(f'[Polling] Unexpected error: {traceback.format_exc(limit=5)}')

        return False

    def replace_device_id(self, url, channel_id):
        """
        If {device_id} in url to replace with real device_id
        """
        device_id = self.db.get_device_id(channel_id)
        if device_id:
            url = url.format(device_id=device_id)
        return url

    def get_response(self, endpoint_conf, credentials, channel_id, cred_key):
        url = endpoint_conf['url']
        method = endpoint_conf['method']
        data = endpoint_conf.get('data')
        params = endpoint_conf.get('params')

        if '{device_id}' in url:
            url = self.replace_device_id(url, cred_key.split('/')[-1])

        response = requests.request(method, url, params=params, data=data,
                                    headers=self.authorization(credentials))

        if response.status_code == requests.codes.ok:
            logger.info('[Polling] polling request successful with {}'.format(cred_key))
            return {
                'response': response.json(),
                'channel_id': channel_id,
                'credentials': credentials
            }
        else:
            logger.warning(f'[Polling] Error in polling request: CHANNEL_ID: {channel_id}; '
                           f'URL: {url}; RESPONSE: {response}')
            return {}
