import time

from base.common.skeleton_base import SkeletonBase
from base.constants import DEFAULT_BEFORE_EXPIRES
from base.exceptions import ChannelTemplateNotFound
from base.helpers import validate_channel
from base.utils import format_response
from typing import Dict

from .router import *
from .webhook import *
from .token_refresher import TokenRefresherManager


class SkeletonDevice(SkeletonBase):

    def __init__(self, mqtt=None):
        super(SkeletonDevice, self).__init__(mqtt)
        # self.DEFAULT_BEFORE_EXPIRES = DEFAULT_BEFORE_EXPIRES
        self.before_expires = settings.config_refresh.get('before_expires_seconds', DEFAULT_BEFORE_EXPIRES)

    @property
    def _swap_url(self) -> str:
        server = settings.api_server
        version = settings.api_version
        client_id = settings.client_id
        url = '{}/{}/managers/{}/swap-credentials'.format(server, version, client_id)
        return url

    @staticmethod
    def _credentials_dict(credentials, sender):
        credentials_dict = {
            'key': sender['key'],
            'value': credentials
        }
        return credentials_dict

    def swap_credentials(self, credentials, sender, token_key='access_token') -> Dict:
        url = self._swap_url

        credentials = self.auth_response(credentials) or {}

        if credentials:
            payload = {
                "client_id": sender.get('client_id', credentials.get('client_id', '')),
                "owner_id": sender.get('owner_id', ''),
                "credentials": {
                    token_key: credentials.get(token_key, '')
                }
            }
            response = requests.request('POST', url, headers=self.header, json=payload)
        else:
            logger.warning("[swap_credentials] Credentials not sent")
            return {}

        if response and response.status_code == 200:
            return response.json()
        else:
            payload.pop('credentials', None)
            self.log(f'Error on request swap credentials. Status code: {response.status_code}; URL: {url}; '
                     f'Payload: {payload}', 3)
            return {}

    def check_manager_client_id(self, owner_id, channel_id, main_credentials, second_credentials=None):
        """
        Check if credentials has manager_client_id. Update credentials calling swap credentials if not
        """
        second_credentials = second_credentials or {}
        credentials = self.auth_response(main_credentials)
        has_error = False
        if 'client_man_id' not in credentials:
            sender = {
                'client_id': credentials.get('client_id'),
                'owner_id': owner_id,
                'key': f"credential-owners/{owner_id}/channels/{channel_id}"
            }
            logger.debug(f"[check_manager_client_id] Will try to swap credentials for sender: {sender}")
            swap_credentials = self.swap_credentials(credentials, sender)
            if swap_credentials:
                credentials['client_man_id'] = swap_credentials.get('client_id')
            else:
                logger.warning("[check_manager_client_id] Invalid swap credentials return with main credentials")
                second_credentials = self.auth_response(second_credentials)
                swap_credentials = self.swap_credentials(second_credentials, sender)
                if swap_credentials:
                    credentials['client_man_id'] = swap_credentials.get('client_id')
                else:
                    logger.warning("[check_manager_client_id] Invalid swap credentials return with secondary credentials")
                    has_error = True

        return credentials, has_error

    def auth_requests(self, sender):
        """
        *** MANDATORY ***
        Receives,
            sender      - A dictionary with keys 'channel_template_id', 'owner_id' and 'client_id'.
        Returns a list of dictionaries with the structure,
        [
            {
                "method" : "<get/post>"
                "url" : "<manufacturer's authorize API uri and parameters>"
                "headers" : {}
            },
            ...
        ]
        If the value of headers is {} for empty header, otherwise it follows the structure as of the
        sample given below.

        "headers" : {
            "Accept": "application/json",
            "Authorization": "Bearer {client_secret}"
        }

        Each dictionary in list represent an individual request to be made to manufacturer's API and
        its position denotes the order of request.
        """
        return NotImplemented

    def get_devices(self, sender, credentials):
        """
        *** MANDATORY ***
        Receives,
            credentials - All persisted user credentials.
            sender      - A dictionary with keys 'channel_template_id', 'owner_id' and  'client_id'.
        Returns a list of dictionaries with the following structure ,

        [
            {
                "content" : "<device name>",
                "id" : "<manufacturer's device ID>",
                "photoUrl" : "<url to device's image in cdn.muzzley.com>"
            },
            ...
        ]

        Each dictionary in list denotes a device of user.
        """
        return NotImplemented

    def update_channel_template(self, device_id):
        """
        This method is used to return a channel_template other than the one sent in request on select_devices
        :param device_id: Dict of device characteristcs
        :return: new_channel_id or None
        """
        return None

    def did_pair_devices(self, credentials, sender, paired_devices, channels):
        """
        *** MANDATORY ***
        Invoked after successful device pairing.

        Receives,
            credentials - All persisted user credentials.
            sender - A dictionary:
             {'channel_template_id': xxxx-xxxxx-xxxxx-xxxx,
              'owner_id': xxxx-xxxxx-xxxxx-xxxx,
              'client_id': xxxx-xxxxx-xxxxx-xxxx}
            paired_devices - A list of dictionaries with selected device's data
            channels - A list of channels_id from paired_devices
        """
        return NotImplemented

    def access_check(self, mode, case, credentials, sender):
        """
        *** MANDATORY ***
        Checks for access to manufacture for a component, replace if requires a different process

        Receives,
            mode        - 'r' or 'w'
                r - read from manufacturer's API
                w - write to manufacturer's API
            case       - A dictionary with keys 'device_id','channel_id','component' and 'property'.
            credentials - credentials of user from database
            sender      - A dictionary with keys 'owner_id' and
                        'client_id'.

        Returns updated valid credentials or current one  or None if no access
        """

        try:
            now = int(time.time())
            expiration_date = credentials['expiration_date']

            if 'key' in sender:
                if now >= expiration_date:  # we should refresh the token
                    self.log('[access_check] token is expired trying to refresh {}'.format(sender['key']), 7)
                    credentials_dict = self._credentials_dict(credentials, sender)
                    credentials = self.refresh_token(credentials_dict)

            return credentials

        except KeyError as e:
            self.log('Error: missing {} key'.format(e), 4)
        except Exception:
            self.log('Unexpected error {}'.format(traceback.format_exc(limit=5)), 3)

        self.log(f'Missing info in access_check: \nsender: {sender} \ncase:{case}', 9)

        return None

    def polling(self, data):
        """
        Invoked by the manager itself when performing a polling request to manufacturer's API

        Receives,
            data - A dictionary with keys 'channel_id', 'credentials' and 'response' where response is a json object

        This function is in charge
        """
        raise NotImplementedError('No polling handler implemented')

    def get_channel_template(self, channel_id):
        """
        Input :
            channel_id - channel_id of the device.

        Returns channel_template_id

        """
        channel = validate_channel(channel_id)
        return channel['channeltemplate_id'] if (channel and 'channeltemplate_id' in channel) else ''

    def get_channels_by_channeltemplate(self, channeltemplate_id):
        """
        Input :
            channeltemplate_id - channeltemplate_id of the device.

        Returns list of channels_id

        """
        try:
            if not channeltemplate_id:
                logger.warning(f"[get_channels_by_channeltemplate] Invalid channeltemplate_id")
                return ''
            url = f"{settings.api_server_full}/managers/{settings.client_id}/channels?" \
                  f"page_size=9999&channel.channeltemplate_id={channeltemplate_id}&fields=channel.id"

            resp = requests.get(url, headers=self.header)
            logger.verbose("[get_channels_by_channeltemplate] Received response code[{}]".format(resp.status_code))

            if int(resp.status_code) == 200:
                return [client_channel.get('channel', {}).get("id") for client_channel in
                        resp.json().get("elements", [])]
            else:
                raise ChannelTemplateNotFound("Failed to retrieve channel_ids for {}".format(channeltemplate_id))

        except (OSError, ChannelTemplateNotFound) as e:
            logger.warning('[get_channels_by_channeltemplate] Error while making request to platform: {}'.format(e))
        except Exception:
            logger.alert("[get_channels_by_channeltemplate] Unexpected error: {}".format(traceback.format_exc(limit=5)))
        return ''

    def get_channel_by_owner(self, owner_id, channel_id):
        """
        Input :
            owner_id
            channel_id

        Returns channeltemplate_id

        """

        url = "{}/users/{}/channels?channel_id={}".format(settings.api_server_full, owner_id, channel_id)

        try:
            resp = requests.get(url, headers=self.header)

            if int(resp.status_code) == 200:
                return resp.json()['elements'][0]['channel']["channeltemplate_id"]
            elif int(resp.status_code) == 204:  # No content
                logger.verbose("[get_channel_by_owner] Received response code[{}]".format(resp.status_code))
                return False
            else:
                logger.verbose("[get_channel_by_owner] Received response code[{}]".format(resp.status_code))
                raise ChannelTemplateNotFound(f"[get_channel_by_owner] Failed to retrieve channel_template_id "
                                              f"for {channel_id}")

        except (OSError, ChannelTemplateNotFound) as e:
            logger.warning('[get_channel_by_owner] Error while making request to platform: {}'.format(e))
        except Exception:
            logger.alert("[get_channel_by_owner] Unexpected error: {}".format(traceback.format_exc(limit=5)))
        return ''

    def get_device_id(self, channel_id):
        """
        To retrieve device_id using channel_id

        """
        return self.db.get_device_id(channel_id)

    def get_channel_id(self, device_id):
        """
        To retrieve channel_id using device_id

        """
        return self.db.get_channel_id(device_id)

    def get_polling_conf(self):
        """
        Required configuration if polling is enabled
        Returns a dictionary or a list of dictionaries:
            {
                url (required): polling manufacturer url
                method (required): HTTP method to use: GET / POST
                params: URL parameters to append to the URL (used by requests)
                data: the body to attach to the request (used by requests)
            }
        """
        raise NotImplementedError('polling ENABLED but conf NOT DEFINED')

    # -------------
    # TOKEN REFRESH
    # -------------

    def get_refresh_token_conf(self):
        """
        Required configuration if token refresher is enabled
        Returns a dictionary
            url - token refresh manufacturer url
            headers - if required a dict with necessary headers
        """
        raise NotImplementedError('token refresher ENABLED but conf NOT DEFINED')

    def refresh_token(self, credentials_dict):
        refresh_token = credentials_dict.get('value', {}).get('refresh_token', '')
        refresher = TokenRefresherManager(implementer=self)
        conf = self.get_refresh_token_conf()

        response = refresher.send_request(refresh_token, credentials_dict, conf)
        self.log('refresh_token response {}'.format(response), 7)

        if type(response) is dict and 'credentials' in response:
            self.after_refresh(response)
            return response['credentials']
        return None

    def after_refresh(self, data):
        """
        Invoked by the manager itself when successfully refreshing a token

        Receives,
            data - A dictionary with keys 'channel_id' and 'new_credentials'

        + not required +
        """
        pass

    def update_expiration_date(self, credentials):
        now = int(time.time())
        expires_in = int(credentials['expires_in']) - self.before_expires
        expiration_date = now + expires_in
        credentials['expiration_date'] = expiration_date

        return credentials

    def store_credentials(self, owner_id, client_app_id, channeltemplate_id, credentials):

        try:
            url = f"{settings.api_server_full}/managers/{settings.client_id}/store-credentials"
            payload = {
                'client_id': client_app_id,
                'owner_id': owner_id,
                'channeltemplate_id': channeltemplate_id,
                'credentials': credentials
            }
            if not (client_app_id and owner_id and channeltemplate_id and credentials):
                logger.warning(f'[store_credentials] Invalid payload request client_id: {client_app_id}; '
                               f'owner_id: {owner_id}; channeltemplate_id: {channeltemplate_id}')
                return False
            logger.verbose(f"[store_credentials] Try to update credentials for channeltemplate_id {channeltemplate_id}")
            resp = requests.post(url, headers=self.header, json=payload)
            logger.verbose(f"[store_credentials] Received response code[{resp.status_code}]")

            if int(resp.status_code) == 200 and resp.json().get('n_updated'):
                return True
            elif int(resp.status_code) == 200 and resp.json().get('n_updated', 0) == 0:
                payload.pop('credentials', None)
                logger.warning(f'[store_credentials] credentials not found to patch with requested data: '
                               f'{payload}')
                return False
            else:
                logger.warning(f'[store_credentials] Error while making request to platform: {format_response(resp)}')
                return False

        except Exception:
            logger.alert(f"[store_credentials] Unexpected error store_credentials: {traceback.format_exc(limit=5)}")
        return False


SkeletonBase.register(SkeletonDevice)
