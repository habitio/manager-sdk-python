import json
from abc import ABC, abstractmethod
from datetime import timedelta

from base import settings, logger
from base.redis_db import get_redis
from base.exceptions import ChannelTemplateNotFound, PropertyHistoryNotFoundException, InvalidRequestException
from base.logger_base import LOG_TABLE
import requests
import traceback


class SkeletonBase(ABC):

    def __init__(self, queue=None, thread_pool=None):
        super(SkeletonBase, self).__init__()
        self._type = settings.implementor_type
        self.db = get_redis()
        self.queue = queue
        self.confirmation_hash = ""
        self.thread_pool = thread_pool

    @property
    def header(self):
        return {
            "Authorization": "Bearer {0}".format(settings.block["access_token"]),
            "Accept": "application/json",
        }

    @abstractmethod
    def start(self):
        """
        Initial setup
        """
        return NotImplemented

    @staticmethod
    def _clear_response_data(response_data):
        if response_data.get('access_token_expires_in'):
            response_data['expires_in'] = int(response_data.pop('access_token_expires_in', 0))
        else:
            response_data['expires_in'] = response_data.get('expires_in', 0)
        response_data['expiration_date'] = response_data.get('expiration_date', 0)

        return response_data

    def route_setup(self, app):
        """
        Route setup for Manager implementation
        :param app: Flask app object
        :return: None
        """
        pass

    def auth_response(self, response_data):
        """
        *** MANDATORY ***
        Receives the response from manufacturer's API after authorization.

        Returns dictionary of required credentials for persistence, otherwise
        returns None if no persistence required after analyzing.

        dictionary template:
        {
            'access_token': '{access_token}',
            'refresh_token': '{refresh_token}',
            'token_type': '{token_type}',
            'expires_in': {expires_in},
            'expiration_date': {expiration_date},
            'client_id': '{client_id}'
        }
        """
        return NotImplemented

    def upstream(self, mode, case, credentials, sender, data=None):
        """
        *** MANDATORY ***
        Invoked when Muzzley platform intends to communicate with manufacturer's api
        to read/update device's information.

        Receives,
            mode        - 'r' or 'w'
                r - read from manufacturer's API
                w - write to manufacturer's API
            case       - A dictionary with keys 'device_id','channel_id','component' and 'property'.
            data        - data if any sent by Muzzley's platform.
            credentials - credentials of user from database
            sender      - A dictionary with keys 'owner_id' and
                        'client_id'.

        Expected Response,
            'r' - mode
                Returns data on successful read from manufacturer's API, otherwise
                returns None.
            'w' - mode
                Returns True on successful write to manufacturer's API, otherwise
                returns False.
        """
        return NotImplemented

    def downstream(self, request):
        """
        *** MANDATORY ***
        Invoked when manufacturer's api intends to communicate with Muzzley's platform
        to update device's information.

        Receives,
            request - A flask.request object received from manufacturer's API.

        Returns a tuple as (case, data),
            case - Expecting a dictionary with keys 'device_id' or 'channel_id', 'component' and 'property',
                   otherwise if None is returned for case, then NO data will be send to muzzley
            data - Any data that has to be send to Muzzley's platform
            status_code (optional) - http status code, if not defined 200 status is set as default


        """
        return NotImplemented

    def get_channel_status(self, channel_id):
        """
        To retrieve channel status using channel_id

        """
        return self.db.get_channel_status(channel_id)

    def store_channel_status(self, channel_id, status):
        """
        To store a value to database with a unique identifier called key

        """
        self.db.set_channel_status(channel_id, status)

    def get_all_credentials(self):
        """
        Get a full list of existing credentials with corresponding key

        """
        credentials_list = self.db.full_query('credential-owners/*/channels/*')
        return credentials_list

    def store(self, key, value):
        """
        To store a value to database with a unique identifier called key

        """
        self.db.set_key(key, value)

    def retrieve(self, key):
        """
        To retireve a value from database with its unique identifier, key.

        """
        return self.db.get_key(key)

    def exists(self, key):
        """
        To check if a key is already present in database.

        """
        return self.db.has_key(key)

    def log(self, message, level):
        """
        To log a message to log file
            message - message to be logged.
            level   - denotes the logging priority. The level-priority relation given below,

                priority    -level
                ------------------
                emergency   = 0,
                alert       = 1,
                critical    = 2,
                error       = 3,
                warning     = 4,
                notice      = 5,
                info        = 6,
                debug       = 7,
                trace       = 8,
                verbose     = 9
        """
        try:
            LOG_TABLE[level](message)
        except IndexError as ex:
            logger.error(str(ex))

    def get_config(self):
        """
        Returns the entire data in configuration file.

        """
        return settings.get_config()

    def publisher(self, case, data):
        """
        To make an mqtt publish
            case - a dictionary with keys  'device_id', 'component' and 'property'
            data - data to be published
        """
        self.log("Will publisher to mqtt", 7)
        self.queue.put({
            "io": "iw",
            "data": data,
            "case": case
        })

    def renew_credentials(self, channel_id, sender, credentials):
        """
        To update credentials in database
            channel_id - channel_id of the device.
            credentials - a dictionary with data to be updated.
            sender      - a dictionary with keys 'owner_id' and
                        'client_id'.
        """
        try:
            self.db.set_credentials(
                credentials, sender["client_id"], sender["owner_id"], channel_id)
            self.log("Credentials successfully renewed !", 6)
        except Exception as ex:
            self.log("Renew credentials failed!!! {}".format(traceback.format_exc(limit=5)), 4)

    def get_type(self):
        return self._type

    def format_datetime(self, _value):
        _tr = _value + timedelta(milliseconds=0.5)
        return '{}.{}+0000'.format(_tr.strftime('%Y-%m-%dT%H:%M:%S'), _tr.strftime('%f')[:3])

    def route(self, _method, _topic, _payload={}, _headers={}):

        __headers = {
            "Authorization": "Bearer {}".format(settings.block["access_token"]),
            "Content-Type": "application/json"
        }

        if _headers:
            __headers.update(_headers)

        _topic = '{}{}'.format(settings.api_server, _topic)

        self.log('Request: {} {} - PAYLOAD: {}'.format(_method.upper(), _topic, _payload), 9)

        _response = requests.request(
            _method,
            _topic,
            data=json.dumps(_payload),
            headers=__headers
        )

        self.log('Response: {} {} - STATUS CODE: {} PAYLOAD: {}'.format(_method.upper(), _topic, _response.status_code, _response.text), 9)

        return _response

    def get_channeltemplate_data(self, channeltemplate_id):
        """
        Input :
            channeltemplate_id - Muzzley channeltemplate_id

        Returns channel_template_id

        """

        url = "{}/channel-templates/{}".format(settings.api_server_full, channeltemplate_id)
        headers = {
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        }
        try:
            resp = requests.get(url, headers=headers)

            if int(resp.status_code) == 200:
                return resp.json()
            else:
                self.log("[get_channeltemplate_data] Received response code[{}]".format(resp.status_code), 9)
                raise ChannelTemplateNotFound("Failed to retrieve channeltemplate_data {}".format(channeltemplate_id))

        except (OSError, ChannelTemplateNotFound) as e:
            self.log('[get_channeltemplate_data] Error while making request to platform: {}'.format(e), 3)
        except Exception as ex:
            self.log("[get_channeltemplate_data] Unexpected error get_channeltemplate_data: {}".format(traceback.format_exc(limit=5)), 3)
        return {}

    def get_property_history(self, channel_id, component, property_, params=None):
        params = params or {}
        url = "{}/channels/{channel_id}/components/{component}/properties/{property}/history".format(
            settings.api_server_full, channel_id=channel_id, component=component, property=property_
        )

        headers = {
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        }
        try:
            resp = requests.get(url, headers=headers, params=params)

            if int(resp.status_code) == 200:
                return resp.json()["elements"]
            else:
                self.log("[get_property_history] Received response code[{}]".format(resp.status_code), 9)
                raise PropertyHistoryNotFoundException("Failed to retrieve property_history")

        except (OSError, PropertyHistoryNotFoundException) as e:
            self.log('[get_property_history] Error while making request to platform: {}'.format(e), 3)
        except Exception:
            self.log("[get_property_history] Unexpected error get_property_history: {}".format(
                traceback.format_exc(limit=5)), 3)
        return []

    def get_latest_property_value(self, channel_id, component, property_):
        try:
            resp = self.get_property_history(channel_id, component, property_)
            return resp[0]["value"]

        except (OSError, PropertyHistoryNotFoundException) as e:
            self.log('[get_latest_property_value] Error while making request to platform: {}'.format(e), 3)
        except Exception:
            self.log("[get_latest_property_value] Unexpected error get_latest_property_value: {}".format(
                traceback.format_exc(limit=5)), 3)
        return {}

    def get_user_subscriptions(self, channel_id):
        url = f"{settings.api_server_full}/channels/{channel_id}/retrieve-user-subscriptions"

        headers = {
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        }
        try:
            resp = requests.post(url, headers=headers)

            if int(resp.status_code) == 200:
                return resp.json()["elements"]
            else:
                self.log("[get_user_subscriptions] Received response code[{}]".format(resp.status_code), 9)
                raise InvalidRequestException("Failed to retrieve user subscriptions")

        except (OSError, InvalidRequestException) as e:
            self.log('[get_user_subscriptions] Error while making request to platform: {}'.format(e), 3)
        except Exception:
            self.log("[get_user_subscriptions] Unexpected error get_user_subscriptions: {}".format(
                traceback.format_exc(limit=5)), 3)
        return {}

    # -------------
    # TOKEN REFRESH
    # -------------

    def get_params(self, url, credentials):
        """
        Create params dict to be sent in token_refresher request
        :param url:
        :param credentials:
        :return: url (string), params (dict)

        toDo: Delete
        """
        try:
            client_app_id = credentials['client_id']
            manufacturer_client_id = settings.config_manufacturer['credentials'][client_app_id].get('app_id')
            manufacturer_client_secret = settings.config_manufacturer['credentials'][client_app_id].get('app_secret')
        except KeyError:
            self.log('[TokenRefresher] Credentials not found for {}'.format(client_app_id), 7)
            return None, None

        params = {
            'grant_type': 'refresh_token',
            'refresh_token': credentials['refresh_token'],
            'client_id': manufacturer_client_id
        }

        if manufacturer_client_secret is not None:
            params['client_secret'] = manufacturer_client_secret

        return url.split('?')[0], params

    def get_headers(self, credentials, headers):
        """
        Create headers to send with token_refresher request
        :param credentials:
        :param headers:
        :return: headers
        """
        return headers
