import concurrent

from base.redis_db import db
from base.settings import settings
from base.utils import rate_limited
from base.constants import DEFAULT_POLLING_INTERVAL, DEFAULT_RATE_LIMIT, DEFAULT_THREAD_MAX_WORKERS
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
        self.interval = settings.config_polling.get('interval_seconds', DEFAULT_POLLING_INTERVAL)  # default 60 sec.
        self.client_id = settings.client_id
        self.loop = asyncio.new_event_loop()

    def start(self):
        """
        If polling is enabled in config file, retrieves conf for polling in implementor
        """
        try:
            from base.solid import implementer
            if settings.config_polling.get('enabled') == True:
                logger.info('[Polling] **** starting polling ****')
                t = threading.Thread(target=self.worker, args=[implementer.get_polling_conf()], name="Polling")
                t.start()
            else:
                logger.info('[Polling] **** polling is not enabled ****')
        except NotImplementedError as e:
            logger.error("[Polling] NotImplementedError: {}".format(e))
        except Exception as e:
            logger.alert("[Polling] Unexpected exception: {} {}".format(e, traceback.format_exc(limit=5)))

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
                logger.error('[Polling] Error on worker loop, preventing to break thread, {}'.format(traceback.format_exc(limit=5)))
            time.sleep(self.interval)

    async def make_requests(self, conf_data: dict):
        from base.solid import implementer
        logger.info("[Polling] {} starting {}".format(threading.currentThread().getName(),  datetime.datetime.now()))

        url = conf_data['url']
        method = conf_data['method']
        data = conf_data.get('data')
        params = conf_data.get('params')

        loop = asyncio.get_event_loop()

        with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_THREAD_MAX_WORKERS) as executor:
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

        logger.info("[Polling] {} finishing {}".format(threading.currentThread().getName(),  datetime.datetime.now()))

    @rate_limited(settings.config_polling.get('rate_limit', DEFAULT_RATE_LIMIT))
    def send_request(self, channel_id, method, url, params, data):
        try:
            # validate if channel exists
            from base.solid import implementer
            try:
                channel_template_id = implementer.get_channel_template(channel_id)
            except Exception as e:
                logger.debug('[Polling] {}'.format(e))
                channel_template_id = None

            if not channel_template_id:
                return

            credentials_list = db.full_query('credential-owners/*/channels/{}'.format(channel_id))
            logger.info('[Polling] {} results found for channel_id: {}'.format(len(credentials_list), channel_id))

            for credential_dict in credentials_list:  # try until we find valid credentials
                cred_key = credential_dict['key']
                credentials = credential_dict['value']

                # Validate if token is valid before the request
                now = int(time.time())
                token_expiration_date = credentials['expiration_date']
                if now > token_expiration_date and not token_expiration_date == 0:
                    logger.debug("[Polling] access token expired {} - now:{}, expiration:{}".format(
                        cred_key, now, token_expiration_date))
                    continue

                response = requests.request(method,  url, params=params, data=data, headers=self.authorization(credentials))
                if response.status_code == requests.codes.ok:
                    logger.info('[Polling] polling request successful with {}'.format(cred_key))
                    return {
                        'response': response.json(),
                        'channel_id': channel_id,
                        'credentials': credentials
                    }
                else:
                    logger.warning('[Polling] Error in polling request {} {}'.format(channel_id, response))
        except Exception:
            logger.error('[Polling] Error on polling.send_request {}'.format(traceback.format_exc(limit=5)))
        logger.notice('[Polling] No valid credentials found for channel {}'.format(channel_id))
        return False

try:
    poll = PollingManager()
except Exception as e:
    logger.error("[Polling] Failed start polling manager, {} {}".format(e, traceback.format_exc(limit=5)))
