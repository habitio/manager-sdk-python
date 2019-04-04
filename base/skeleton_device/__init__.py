from base import settings
from base.common.skeleton_base import SkeletonBase
from base.constants import DEFAULT_BEFORE_EXPIRES
from base.exceptions import ChannelTemplateNotFound

from .router import *
from .webhook import *


class SkeletonDevice(SkeletonBase):

    def __init__(self):
        super(SkeletonDevice, self).__init__()
        self.DEFAULT_BEFORE_EXPIRES = DEFAULT_BEFORE_EXPIRES

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

    def did_pair_devices(self, credentials, sender, paired_devices):
        """
        *** MANDATORY ***
        Invoked after successful device pairing.

        Receives,
            credentials     - All persisted user credentials.
            sender          - A dictionary with keys 'channel_template_id', 'owner_id' and 'client_id'.
            paired_devices  - A list of dictionaries with selected device's data

        """
        return NotImplemented

    def access_check(self, mode, case, credentials, sender):
        """
        *** MANDATORY ***
        Checks for access to manufacture for a component

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
        return NotImplemented

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

        url = "{}/channels/{}".format(settings.api_server_full, channel_id)
        headers = {
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        }
        try:
            resp = requests.get(url, headers=headers)
            logger.verbose("Received response code[{}]".format(resp.status_code))

            if int(resp.status_code) == 200:
                return resp.json()["channeltemplate_id"]
            else:
                raise ChannelTemplateNotFound("Failed to retrieve channel_template_id for {}".format(channel_id))

        except (OSError, ChannelTemplateNotFound) as e:
            logger.warning('Error while making request to platform: {}'.format(e))
        except Exception as ex:
            logger.alert("Unexpected error get_channel_template: {}".format(traceback.format_exc(limit=5)))
        return ''

    def get_channel_by_owner(self, owner_id, channel_id):
        """
        Input :
            owner_id
            channel_id

        Returns channeltemplate_id

        """

        url = "{}/users/{}/channels?channel_id={}".format(settings.api_server_full, owner_id, channel_id)
        headers = {
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        }
        try:
            resp = requests.get(url, headers=headers)
            logger.verbose("Received response code[{}]".format(resp.status_code))

            if int(resp.status_code) == 200:
                return resp.json()['elements'][0]['channel']["channeltemplate_id"]
            elif int(resp.status_code) == 204:  # No content
                return False
            else:
                raise ChannelTemplateNotFound("Failed to retrieve channel_template_id for {}".format(channel_id))

        except (OSError, ChannelTemplateNotFound) as e:
            logger.warning('Error while making request to platform: {}'.format(e))
        except Exception as ex:
            logger.alert("Unexpected error get_channel_by_owner: {}".format(traceback.format_exc(limit=5)))
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
        Returns a dictionary
            url - polling manufacturer url
            method - HTTP method to use: GET / POST
            params - URL parameters to append to the URL (used by requests)
            data - the body to attach to the request (used by requests)
        """
        raise NotImplementedError('polling ENABLED but conf NOT DEFINED')

    def get_refresh_token_conf(self):
        """
        Required configuration if token refresher is enabled
        Returns a dictionary
            url - token refresh manufacturer url
            method - HTTP method to use: GET / POST
        """
        raise NotImplementedError('token refresher ENABLED but conf NOT DEFINED')

    def after_refresh(self, data):
        """
        Invoked by the manager itself when successfully refreshing a token

        Receives,
            data - A dictionary with keys 'channel_id' and 'new_credentials'

        + not required +
        """
        pass


SkeletonBase.register(SkeletonDevice)
