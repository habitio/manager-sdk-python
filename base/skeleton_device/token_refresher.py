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
from typing import Iterable


class TokenRefresherManager(object):

    def __init__(self, implementer=None):
        self.interval = settings.config_refresh.get('interval_seconds', DEFAULT_REFRESH_INTERVAL)  # default 60 sec.
        self.client_id = settings.client_id
        self.loop = asyncio.new_event_loop()
        self.before_expires = settings.config_refresh.get('before_expires_seconds', DEFAULT_BEFORE_EXPIRES)
        self.thread = None
        self.db = get_redis()
        self.implementer = implementer
        self._channel_relations = {}
        self._channel_template = None

    @property
    def channel_relations(self):
        return self._channel_relations

    @channel_relations.deleter
    def channel_relations(self):
        self.channel_relations.clear()

    @property
    def channel_template(self):
        return self._channel_template

    @channel_template.setter
    def channel_template(self, value):
        self._channel_template = value

    @channel_template.deleter
    def channel_template(self):
        self._channel_template = None

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
        except Exception:
            logger.alert("[TokenRefresher] Unexpected exception: {} {}".format(traceback.format_exc(limit=5)))

    def worker(self, conf_data):
        asyncio.set_event_loop(self.loop)
        loop = asyncio.get_event_loop()

        while True:
            logger.info('[TokenRefresher] new refresh process {}'.format(datetime.datetime.now()))
            loop.run_until_complete(self.make_requests(conf_data))
            time.sleep(self.interval)
            del self.channel_relations

    def get_credentials_by_refresh_token(self, refresh_lookup=None):
        credentials_redis = self.db.full_query('credential-owners/*/channels/*')
        credentials = {}
        for cred_dict in credentials_redis:
            cred_dict['value'] = self.implementer.auth_response(cred_dict['value'])
            refresh_token = cred_dict['value'].get('refresh_token')
            if not refresh_lookup or refresh_lookup == refresh_token:
                try:
                    credentials[refresh_token].append(cred_dict)
                except KeyError:
                    credentials[refresh_token] = [cred_dict]
        return credentials if not refresh_lookup or refresh_lookup not in credentials else credentials[refresh_lookup]

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
                        refresh_token, credentials, conf_data
                    )
                    for refresh_token, credentials in self.get_credentials_by_refresh_token().items()
                ]
                for response in await asyncio.gather(*futures):
                    if response:
                        self.implementer.after_refresh(response)

            logger.info("[TokenRefresher] {} finishing {}".format(threading.currentThread().getName(),
                                                                  datetime.datetime.now()))
        except Exception:
            logger.error(f"[TokenRefresher] Error on make_requests: {traceback.format_exc(limit=5)}")

    @rate_limited(settings.config_refresh.get('rate_limit', DEFAULT_RATE_LIMIT))
    def send_request(self, refresh_token, credentials_list, conf):
        try:
            if credentials_list and type(credentials_list) is not list:
                credentials_list = [credentials_list]

            if not credentials_list:
                return

            try:
                url = conf['url']
            except KeyError as e:
                logger.error(f'[TokenRefresher] Missing key {e} on refresh conf')
                return
            if not url:
                logger.warning(f'[TokenRefresher] Missing URL conf: {conf}')
                return
            headers = conf.get('headers', {})

            # try refresh with all credentials in credentials_list until find a valid one
            for credentials_dict in credentials_list:
                has_error = False
                key = credentials_dict['key']  # credential-owners/[owner_id]/channels/[channel_id]
                channel_id = key.split('/')[-1]
                owner_id = key.split('/')[1]
                credentials = credentials_dict['value']

                try:
                    client_app_id = credentials['client_id']
                except KeyError:
                    logger.debug(f'[TokenRefresher] Missing client_id for {key}')
                    continue

                # Validate if token contain all required data
                required_keys = {'expiration_date', 'expires_in', 'refresh_token', 'access_token'}
                if not all(k in credentials for k in required_keys):
                    credentials = self.implementer.auth_response(credentials)
                    self.db.set_credentials(credentials, client_app_id, owner_id, channel_id)
                    if not all(k in credentials for k in required_keys):
                        logger.debug(f'[TokenRefresher] Missing required data for {key}')
                        continue

                token_expiration_date = credentials['expiration_date']
                now = int(time.time())

                if now >= (token_expiration_date - self.before_expires):
                    logger.info(f"[TokenRefresher] Refreshing token {key}")
                    logger.info(f"[TokenRefresher] client_app_id: {client_app_id}; owner_id: {owner_id}; "
                                f"channel_id: {channel_id}")
                    params = "grant_type=refresh_token&client_id={client_id}&client_secret={client_secret}" \
                             "&refresh_token=" + refresh_token

                    refresh_headers = self.implementer.get_headers(credentials, headers)

                    data = {
                        "location": {
                            "method": "POST",
                            "url": f'{url}?{params}',
                            "headers": refresh_headers
                        }
                    }

                    request_headers = {
                        "Authorization": f"Bearer {settings.block['access_token']}",
                        "X-Client-ID": client_app_id,
                        "X-Owner-ID": owner_id,
                        "X-Channel-ID": channel_id,
                        "X-Refresh-Token": refresh_token
                    }

                    response = requests.request("POST", settings.refresh_token_url, json=data, headers=request_headers)

                    if response.status_code == requests.codes.ok:
                        new_credentials = self.implementer.auth_response(response.json())
                        new_credentials = self.implementer.update_expiration_date(new_credentials)

                        if 'refresh_token' not in new_credentials:  # we need to keep same refresh_token always
                            new_credentials['refresh_token'] = refresh_token
                        if not credentials.get('client_man_id'):
                            credentials, has_error = self.implementer.check_manager_client_id(
                                owner_id, channel_id, credentials, new_credentials)
                        new_credentials['client_man_id'] = credentials.get('client_man_id')
                        logger.debug(f"[TokenRefresher] Update new credentials in DB")
                        self.db.set_credentials(new_credentials, client_app_id, owner_id, channel_id)

                        # Check list size because this could be called from implementer.access_check
                        if len(credentials_list) == 1:
                            logger.debug(f"[TokenRefresher] Trying to find credentials using old refresh token")
                            credentials_list = self.get_credentials_by_refresh_token(credentials['refresh_token'])
                        credentials_list = [cred_ for cred_ in credentials_list if cred_['key'] != key]

                        self.update_credentials(new_credentials, credentials_list)

                        return {
                            'channel_id': channel_id,
                            'credentials': new_credentials,
                            'old_credentials': credentials,
                            'new': True
                        }
                    elif response.status_code == requests.codes.bad_request and "text" in response.json():
                        logger.warning(f"[TokenRefresher] channel_id: {channel_id}, {response.json()['text']}")
                        has_error = True
                    else:
                        logger.warning(f'[TokenRefresher] Error in refresh token request {channel_id} {response}')
                        has_error = True
                else:
                    logger.debug(f"[TokenRefresher] access token hasn't expired yet {key}")
                if credentials_list.index(credentials_dict) + 1 < len(credentials_list):
                    logger.debug(f"[TokenRefresher] Will try next credentials in list")
                    continue
                if not has_error:
                    return {
                        'channel_id': channel_id,
                        'credentials': credentials,
                        'old_credentials': credentials,
                        'new': False
                    }

        except Exception:
            logger.error(f'[TokenRefresher] Unexpected error on send_request for refresh token, '
                         f'{traceback.format_exc(limit=5)}')

    def update_all_owners(self, new_credentials, channel_id, ignore_keys=None):
        ignore_keys = ignore_keys or []
        all_owners_credentials = self.db.full_query(f'credential-owners/*/channels/{channel_id}')
        all_owners_credentials = list(filter(lambda x: x['key'] not in ignore_keys, all_owners_credentials))
        all_owners_credentials = self.check_credentials_man_id(all_owners_credentials, new_credentials)
        error_keys = [cred_['key'] for cred_ in all_owners_credentials if cred_.get('has_error', False) is True]
        all_owners_credentials = self.filter_credentials(all_owners_credentials, new_credentials.get('client_man_id'))
        logger.info(f'[update_all_owners] {len(all_owners_credentials)} keys to update for channel {channel_id}')
        updated_cred = []
        if all_owners_credentials:
            updated_, error_ = self.update_credentials(new_credentials, all_owners_credentials)
            updated_cred.extend(updated_)
            updated_cred.extend(ignore_keys)
            updated_cred.extend(error_)
            for owner_credentials in all_owners_credentials:
                owner_id = owner_credentials['key'].split('/')[1]
                logger.verbose(f'[update_all_owners] Trying to update all credentials for the owner: {owner_id}')
                updated_cred.extend(self.update_all_channels(new_credentials, owner_id, updated_cred))
        return list(set(updated_cred)), list(set(error_keys))

    def update_all_channels(self, new_credentials, owner_id, ignore_keys=None):
        ignore_keys = ignore_keys or []
        all_channels_credentials = self.db.full_query(f'credential-owners/{owner_id}/channels/*')
        all_channels_credentials = list(filter(lambda x: x['key'] not in ignore_keys, all_channels_credentials))
        logger.info(f'[update_all_channels] {len(all_channels_credentials)} keys to update for owner {owner_id}')
        updated_cred = []
        if all_channels_credentials:
            updated_, error_ = self.update_credentials(new_credentials, all_channels_credentials)
            updated_cred.extend(updated_)
            ignore_keys.extend(updated_)
            ignore_keys.extend(error_)
            for channel_credentials in all_channels_credentials:
                channel_id = channel_credentials['key'].split('/')[-1]
                logger.verbose(f'[update_all_channels]  Trying to update all credentials for the channel: {channel_id}')
                updated_, error_keys = self.update_all_owners(new_credentials, channel_id, ignore_keys)
                updated_cred.extend(updated_)
                ignore_keys.extend(updated_)
                ignore_keys.extend(error_)
        return list(set(updated_cred))

    def update_credentials(self, new_credentials, old_credentials_list):
        """
        Update all credentials in old_credentials_list with new_credentials
        :param new_credentials: dict
        :param old_credentials_list: [{
            'key': ':credential_key',
            'value': :credential_dict
        }, ...]
        """
        old_credentials_list = self.check_credentials_man_id(old_credentials_list, new_credentials)
        error_keys = [cred_['key'] for cred_ in old_credentials_list if cred_['has_error'] is True]
        old_credentials_list = self.filter_credentials(old_credentials_list, new_credentials.get('client_man_id'))
        updated_credentials = []
        logger.info(f'[TokenRefresher] update_credentials: {len(old_credentials_list)} keys to update')
        for cred_ in old_credentials_list:
            key = cred_['key']
            credentials = cred_['value']
            channel_id = key.split('/')[-1]
            owner_id = key.split('/')[1]

            client_app_id = credentials.get('client_id', credentials.get('data', {}).get('client_id', ''))
            client_man_id = credentials.get('client_man_id')
            # replace client_id in new credentials with current client_app_id and client_man_id
            # to keep consistence with different apps
            new_credentials['client_id'] = client_app_id
            new_credentials['client_man_id'] = client_man_id
            try:
                channeltemplate_id = self.channel_relations[channel_id]
            except KeyError:
                channeltemplate_id = self.implementer.get_channel_template(channel_id)

            if channeltemplate_id and \
                    (settings.config_boot.get('on_pair', {}).get('update_all_channeltemplates', True)
                     or channeltemplate_id == self.channel_template):
                logger.debug(f'[update_credentials] new credentials {key}')
                logger.info(f"[update_credentials] client_app_id: {client_app_id}; owner_id: {owner_id}; "
                            f"channel_id: {channel_id}; channeltemplate_id: {channeltemplate_id}")
                self.channel_relations[channel_id] = channeltemplate_id
                stored = self.implementer.store_credentials(owner_id, client_app_id, channeltemplate_id,
                                                            new_credentials)
                if stored:
                    self.db.set_credentials(new_credentials, client_app_id, owner_id, channel_id)
                    updated_credentials.append(key)
                else:
                    logger.verbose(f'[update_credentials] Ignoring key {key}')
                    error_keys.append(key)
            else:
                logger.verbose(f'[update_credentials] Ignoring key {key}')
                error_keys.append(key)

        return list(set(updated_credentials)), list(set(error_keys))

    def check_credentials_man_id(self, credentials_check, new_credentials):
        if type(credentials_check) is not list:
            credentials_check = [credentials_check]
        if not credentials_check:
            return credentials_check
        for cred_ in credentials_check:
            key = cred_['key']
            cred_value = cred_['value']
            channel_id = key.split('/')[-1]
            owner_id = key.split('/')[1]

            cred_['value'], cred_['has_error'] = self.implementer.check_manager_client_id(
                owner_id, channel_id, cred_value, new_credentials)
        return credentials_check

    def filter_credentials(self, credentials_list, value, attr='client_man_id', remove_errors=True):
        credentials_list = list(filter(lambda x: x['value'].get(attr) == value, credentials_list))
        if remove_errors:
            credentials_list = list(filter(lambda x: x.get('has_error', False) is False, credentials_list))

        return credentials_list
