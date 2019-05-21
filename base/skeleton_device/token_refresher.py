import concurrent

from base import settings
from base.redis_db import get_redis
from base.utils import rate_limited
from base.constants import DEFAULT_REFRESH_INTERVAL, DEFAULT_RATE_LIMIT, DEFAULT_THREAD_MAX_WORKERS, \
    DEFAULT_BEFORE_EXPIRES, DEFAULT_EXPIRES_IN_KEY
import asyncio
import requests
import threading
import datetime
import logging
import time
import traceback

logger = logging.getLogger(__name__)


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
            if settings.config_refresh.get('enabled') == True:
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
        return self.implementer.update_credentials(credentials_list)

    async def make_requests(self, conf_data: dict):
        try:
            logger.info("[TokenRefresher] {} starting {}".format(threading.currentThread().getName(),
                                                                 datetime.datetime.now()))

            url = conf_data['url']
            method = conf_data['method']

            headers = conf_data.get('headers', {})

            loop = asyncio.get_event_loop()

            with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_THREAD_MAX_WORKERS) as executor:
                futures = [
                    loop.run_in_executor(
                        executor,
                        self.send_request,
                        credentials, method, url, headers
                    )
                    for credentials in self.get_credential_list()
                ]
                for response in await asyncio.gather(*futures):
                    if response:
                        self.implementer.after_refresh(response)

            logger.info("[TokenRefresher] {} finishing {}".format(threading.currentThread().getName(),
                                                                  datetime.datetime.now()))
        except Exception as e:
            logger.error("[TokenRefresher] {} Error on make_requests {}".format(e))

    def get_new_expiration_date(self, credentials):
        now = int(time.time())
        expires_in = int(credentials['expires_in']) - self.before_expires
        expiration_date = now + expires_in
        credentials['expiration_date'] = expiration_date

        return credentials

    def update_all_owners(self, new_credentials, orig_owner_id, channel_id, client_app_id):
        all_owners_credentials = self.db.full_query('credential-owners/*/channels/{}'.format(channel_id))
        logger.info('[TokenRefresher] update_all_owners: {} keys found'.format(len(all_owners_credentials)))
        for cred_dict in all_owners_credentials:
            key = cred_dict['key']
            owner_id = key.split('/')[1]
            if owner_id == orig_owner_id:
                continue  # ignoring original owner
            self.db.set_credentials(new_credentials, client_app_id, owner_id, channel_id)

    @rate_limited(settings.config_refresh.get('rate_limit', DEFAULT_RATE_LIMIT))
    def send_request(self, credentials_dict, method, url, headers, **kwargs):
        try:
            key = credentials_dict['key']  # credential-owners/[owner_id]/channels/[channel_id]
            channel_id = key.split('/')[-1] if 'channel_id' not in kwargs else kwargs['channel_id']
            owner_id = key.split('/')[1] if 'owner_id' not in kwargs else kwargs['owner_id']
            credentials = credentials_dict['value']
            try:
                client_app_id = credentials['client_id']
            except KeyError:
                logger.debug('[TokenRefresher] Missing client_id for {}'.format(key))
                return

            # validate if channel exists
            try:
                channel_template_id = self.implementer.get_channel_by_owner(owner_id, channel_id)
            except Exception as e:
                logger.debug('[TokenRefresher] {}'.format(e))
                channel_template_id = None

            if not channel_template_id:
                return

            # Validate if token is valid before the request
            try:
                now = int(time.time())
                token_expiration_date = credentials['expiration_date']
            except KeyError:
                logger.debug('[TokenRefresher] Missing expiration_date for {}'.format(key))
                return

            if now >= (token_expiration_date - self.before_expires):
                logger.info("[TokenRefresher] Refreshing token {}".format(key))
                url, params = self.implementer.get_params(url, credentials)

                headers = self.implementer.get_headers(credentials, headers)

                response = requests.request(method, url, data=params, headers=headers)

                if response.status_code == requests.codes.ok:
                    new_credentials = self.implementer.auth_response(response.json())

                    if 'refresh_token' not in new_credentials:  # we need to keep same refresh_token always
                        new_credentials['refresh_token'] = credentials['refresh_token']

                    logger.debug('[TokenRefresher] new credentials {}'.format(key))
                    self.db.set_credentials(new_credentials, client_app_id, owner_id, channel_id)

                    if self.update_owners:
                        self.update_all_owners(new_credentials, owner_id, channel_id, client_app_id)
                    return {
                        'channel_id': channel_id,
                        'credentials': new_credentials,
                        'old_credentials': credentials,
                        'new': True
                    }
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
