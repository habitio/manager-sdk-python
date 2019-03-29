import concurrent

from base.redis_db import db
from base.settings import settings
from base.utils import rate_limited
from base.constants import DEFAULT_REFRESH_INTERVAL, DEFAULT_RATE_LIMIT, DEFAULT_THREAD_MAX_WORKERS, DEFAULT_BEFORE_EXPIRES
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
        self.before_expires = settings.config_refresh.get('before_expires_seconds', DEFAULT_BEFORE_EXPIRES)
        self.update_owners = settings.config_refresh.get('update_owners', False)

    def start(self):
        """
        If refreshing token is enabled in config file, retrieves conf for refresh in implementor
        :return:
        """
        try:
            from base.solid import implementer
            if settings.config_refresh.get('enabled') == True:
                logger.info('[TokenRefresher] **** starting token refresher ****')
                t = threading.Thread(target=self.worker, args=[implementer.get_refresh_token_conf()], name="TokenRefresh")
                t.start()
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
        credentials_list = db.full_query('credential-owners/*/channels/*')
        return credentials_list

    async def make_requests(self, conf_data: dict):
        from base.solid import implementer
        logger.info("[TokenRefresher] {} starting {}".format(threading.currentThread().getName(),  datetime.datetime.now()))

        url = conf_data['url']
        method = conf_data['method']
        is_json = conf_data.get('is_json', False)

        loop = asyncio.get_event_loop()

        with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_THREAD_MAX_WORKERS) as executor:
            futures = [
                loop.run_in_executor(
                    executor,
                    self.send_request,
                    credentials, method, url, is_json
                )
                for credentials in self.get_credential_list()
            ]
            for response in await asyncio.gather(*futures):
                if response: implementer.after_refresh(response)

        logger.info("[TokenRefresher] {} finishing {}".format(threading.currentThread().getName(),  datetime.datetime.now()))

    def get_new_expiration_date(self, credentials):
        now = int(time.time())
        expires_in = int(credentials['expires_in']) - self.before_expires
        expiration_date = now + expires_in
        credentials['expiration_date'] = expiration_date

        return credentials

    def update_all_owners(self, new_credentials, orig_owner_id, channel_id, client_app_id):
        all_owners_credentials = db.full_query('credential-owners/*/channels/{}'.format(channel_id))
        logger.info('[TokenRefresher] update_all_owners: {} keys found'.format(len(all_owners_credentials)))
        for cred_dict in all_owners_credentials:
            key = cred_dict['key']
            owner_id = key.split('/')[1]
            if owner_id == orig_owner_id:
                continue  # ignoring original owner
            db.set_credentials(new_credentials, client_app_id, owner_id, channel_id)

    @rate_limited(settings.config_refresh.get('rate_limit', DEFAULT_RATE_LIMIT))
    def send_request(self, credentials_dict, method, url, is_json=False, **kwargs):
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
            from base.solid import implementer
            try:
                channel_template_id = implementer.get_channel_by_owner(owner_id, channel_id)
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
                try:
                    manufacturer_client_id = settings.config_manufacturer['credentials'][client_app_id].get('app_id')
                    manufacturer_client_secret = settings.config_manufacturer['credentials'][client_app_id].get('app_secret')
                except KeyError:
                    logger.debug('[TokenRefresher] Credentials not found for {}'.format(client_app_id))
                    return

                params = {
                    'grant_type': 'refresh_token',
                    'refresh_token': credentials['refresh_token'],
                    'client_id': manufacturer_client_id
                }

                if manufacturer_client_secret is not None:
                    params['client_secret'] = manufacturer_client_secret

                if is_json:
                    response = requests.request(method,  url, json=params)
                else:
                    response = requests.request(method,  url, params=params)

                if response.status_code == requests.codes.ok:
                    new_credentials = self.get_new_expiration_date(response.json())

                    if 'refresh_token' not in new_credentials:  # we need to keep same refresh_token always
                        new_credentials['refresh_token'] = credentials['refresh_token']

                    logger.debug('[TokenRefresher] new credentials {}'.format(key))
                    db.set_credentials(new_credentials, client_app_id, owner_id, channel_id)

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
        except Exception:

            logger.error('[TokenRefresher] Unexpected error on send_request for refresh token, {}'.format(traceback.format_exc(limit=5)))
