import json
from abc import ABC, abstractmethod
from datetime import timedelta

from base.settings import settings
from base.redis_db import db
from base.constants import get_log_table
import requests
import traceback
from base.mqtt_connector import mqtt

LOGGER, LOG_TABLE = get_log_table(__name__)


class SkeletonBase(ABC):

    def __init__(self):
        super(SkeletonBase, self).__init__()
        self._type = settings.implementor_type

    @abstractmethod
    def start(self):
        """
        Initial setup
        """
        return NotImplemented

    def auth_response(self, response_data):
        """
        *** MANDATORY ***
        Receives the response from manufacturer's API after authorization.

        Returns dictionary of required credentials for persistence, otherwise
        returns None if no persistence required after analyzing.
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
                Returns data on successfull read from manufacturer's API, otherwise
                returns None.
            'w' - mode
                Returns True on successfull write to manufacturer's API, otherwise
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
            case - Expecting a dictionary with keys 'device_id', 'component' and 'property',
                   otherwise if None is returned for case, then NO data will be send to muzzley
            data - Any data that has to be send to Muzzley's platform
            response (optional) - flask Response object, if not defined returns a Response with 200 status_code


        """
        return NotImplemented

    def get_channel_status(self, channel_id):
        """
        To retrieve channel status using channel_id

        """
        db.get_channel_status(channel_id)

    def store_channel_status(self, channel_id, status):
        """
        To store a value to database with a unique identifier called key

        """
        db.set_channel_status(channel_id, status)

    def store(self, key, value):
        """
        To store a value to database with a unique identifier called key

        """
        db.set_key(key, value)

    def retrieve(self, key):
        """
        To retireve a value from database with its unique identifier, key.

        """
        return db.get_key(key)

    def exists(self, key):
        """
        To check if a key is already present in database.

        """
        return db.has_key(key)

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
            LOGGER.error(str(ex))

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
        logger.debug("Will publisher to mqtt")
        mqtt.publisher(io="iw", data=data, case=case)

    def renew_credentials(self, channel_id, sender, credentials):
        """
        To update credentials in database
            channel_id - channel_id of the device.
            credentials - a dictionary with data to be updated.
            sender      - a dictionary with keys 'owner_id' and
                        'client_id'.
        """
        try:
            db.set_credentials(
                credentials, sender["client_id"], sender["owner_id"], channel_id)
            logger.info("Credentials successfully renewed !")
        except Exception as ex:
            logger.error("Renew credentials failed!!! {}".format(traceback.format_exc(limit=5)))

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

