import concurrent

from base import settings, logger
from base.redis_db import get_redis
from base.utils import rate_limited
from base.constants import DEFAULT_REFRESH_INTERVAL, DEFAULT_RATE_LIMIT, DEFAULT_THREAD_MAX_WORKERS, \
    DEFAULT_BEFORE_EXPIRES
import asyncio
import requests
import threading
import datetime
import time
import traceback


class TokenRefresherManager(object):

    def __init__(self, implementer=None):
        self.interval = settings.config_refresh.get('interval_seconds', DEFAULT_REFRESH_INTERVAL)  # default 60 sec.
        self.client_id = settings.client_id
        self.loop = asyncio.new_event_loop()
        self.before_expires = settings.config_refresh.get('before_expires_seconds', DEFAULT_BEFORE_EXPIRES)
        self.update_owners = settings.config_refresh.get('update_owners', False)
        self.thread = None
        self.db = get_redis()
        self.implementer = implementer

    def start(self):
        """
        If refreshing token is enabled in config file, retrieves conf for refresh in implementor
        :return:
        """
        try:
            if settings.config_refresh.get('enabled') is True:
                logger.info('[TokenRefresher] **** starting token refresher ****')
                self.thread = threading.Thread(target=self.worker,
                                               args=[self.implementer.get_refresh_token_conf()],
                                               name="TokenRefresh")
                self.thread.daemon = True
                self.thread.start()
            else:
                logger.info('[TokenRefresher] **** token refresher is not enabled ****')
        except NotImplementedError as e:
            logger.error("[TokenRefresher] NotImplementedError: {}".format(e))
        except Exception as e:
            logger.alert("[TokenRefresher] Unexpected exception: {} {}".format(e, traceback.format_exc(limit=5)))

    def worker(self, conf_data):
        asyncio.set_event_loop(self.loop)
        loop = asyncio.get_event_loop()

        while True:
            logger.info('[TokenRefresher] new refresh process {}'.format(datetime.datetime.now()))
            loop.run_until_complete(self.make_requests(conf_data))
            time.sleep(self.interval)

    def get_credential_list(self):
        credentials_list = self.db.full_query('credential-owners/*/channels/*')
        return credentials_list

    async def make_requests(self, conf_data: dict):
        try:
            logger.info("[TokenRefresher] {} starting {}".format(threading.currentThread().getName(),
                                                                 datetime.datetime.now()))

            loop = asyncio.get_event_loop()

            with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_THREAD_MAX_WORKERS) as executor:
                futures = [
                    loop.run_in_executor(
                        executor,
                        self.send_request,
                        credentials, conf_data
                    )
                    for credentials in self.get_credential_list()
                ]
                for response in await asyncio.gather(*futures):
                    if response:
                        self.implementer.after_refresh(response)

            logger.info("[TokenRefresher] {} finishing {}".format(threading.currentThread().getName(),
                                                                  datetime.datetime.now()))
        except Exception as e:
            logger.error("[TokenRefresher] Error on make_requests: {}".format(e))

    @rate_limited(settings.config_refresh.get('rate_limit', DEFAULT_RATE_LIMIT))
    def send_request(self, credentials_dict, conf, **kwargs):
        try:
            key = credentials_dict['key']  # credential-owners/[owner_id]/channels/[channel_id]
            channel_id = key.split('/')[-1] if 'channel_id' not in kwargs else kwargs['channel_id']
            owner_id = key.split('/')[1] if 'owner_id' not in kwargs else kwargs['owner_id']
            credentials = credentials_dict['value']

            try:
                url = conf['url']
                headers = conf.get('headers', {})
            except KeyError as e:
                logger.error('Missing key {} on refresh conf'.format(e))
                return

            try:
                client_app_id = credentials['client_id']
            except KeyError:
                logger.debug('[TokenRefresher] Missing client_id for {}'.format(key))
                return

            # validate if channel exists
            from base.solid import implementer
            try:
                channel_template_id = implementer.get_channel_template(channel_id)
            except Exception as e:
                logger.debug('[TokenRefresher] {}'.format(e))
                channel_template_id = None

            if not channel_template_id:
                return

            # Validate if token is valid before the request
            now = int(time.time())
            for attempt in range(2):
                try:
                    token_expiration_date = credentials['expiration_date']
                    expires_in = credentials['expires_in']
                    refresh_token = credentials['refresh_token']
                    access_token = credentials['access_token']
                    break
                except KeyError:
                    if attempt < 1:
                        credentials = self.implementer.auth_response(credentials)
                        self.db.set_credentials(credentials, client_app_id, owner_id, channel_id)
                    else:
                        logger.debug('[TokenRefresher] Missing expiration_date for {}'.format(key))
                        return

            if now >= (token_expiration_date - self.before_expires):
                logger.info("[TokenRefresher] Refreshing token {}".format(key))
                params = "grant_type=refresh_token&client_id={client_id}&client_secret={client_secret}" \
                         "&refresh_token=" + credentials["refresh_token"]

                if not url and not params:
                    logger.debug('Invalid credentials {}'.format(key))
                    return

                refresh_headers = self.implementer.get_headers(credentials, headers)

                data = {
                    "location": {
                        "method": "POST",
                        "url": '{}?{}'.format(url, params),
                        "headers": refresh_headers
                    }
                }

                request_headers = {
                    "Authorization": "Bearer {}".format(settings.block["access_token"]),
                    "X-Client-ID": client_app_id,
                    "X-Owner-ID": owner_id,
                    "X-Channel-ID": channel_id
                }

                response = requests.request("POST", settings.refresh_token_url, json=data, headers=request_headers)

                if response.status_code == requests.codes.ok:
                    new_credentials = self.implementer.auth_response(response.json())
                    new_credentials = self.implementer.update_expiration_date(new_credentials)

                    if 'refresh_token' not in new_credentials:  # we need to keep same refresh_token always
                        new_credentials['refresh_token'] = credentials['refresh_token']

                    logger.debug('[TokenRefresher] new credentials {}'.format(key))
                    self.db.set_credentials(new_credentials, client_app_id, owner_id, channel_id)

                    if self.update_owners:
                        self.db.update_all_owners(credentials, new_credentials, channel_id)
                        self.db.update_all_channels(credentials, new_credentials, owner_id)
                    return {
                        'channel_id': channel_id,
                        'credentials': new_credentials,
                        'old_credentials': credentials,
                        'new': True
                    }
                elif response.status_code == requests.codes.bad_request and "text" in response.json():
                    logger.debug("channel_id: {}, {}".format(channel_id, response.json()["text"]))

                else:
                    logger.warning('[TokenRefresher] Error in refresh token request {} {}'.format(channel_id, response))
            else:
                logger.debug("[TokenRefresher] access token hasn't expired yet {}".format(key))
                return {
                    'channel_id': channel_id,
                    'credentials': credentials,
                    'old_credentials': credentials,
                    'new': False
                }
        except Exception as e:
            logger.error('[TokenRefresher] Unexpected error on send_request for refresh token, {}'.format(e))
