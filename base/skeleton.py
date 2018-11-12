from abc import ABC, abstractmethod
from base.settings import settings
from base.redis_db import db
import requests
import logging
from base.mqtt_connector import mqtt
from base.polling import PollingManager
from threading import Thread
logger = logging.getLogger(__name__)


class Skeleton(ABC):

    @abstractmethod
    def start(self):
        """
        Initial setup
        """
        pass

    @abstractmethod
    def auth_requests(self, sender):
        """
        *** MANDATORY ***
        Receives,
            sender      - A dictionary with keys 'channel_template_id', 'owner_id' and 'client_id'.
        Returns a list of dictionaries with the structure,
        [
            {
                "method" : "<get/post>"
                "url" : "<manufacturer's authrorize API uri and parameters>"
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

        Each dictionary in list respresent an individual request to be made to manufacturer's API and
        its position denotes the order of request.
        """
        pass

    @abstractmethod
    def auth_response(self, response_data):
        """
        *** MANDATORY ***
        Receives the response from manufacturer's API after authrorization.

        Returns dictionary of required credentials for persistence, otherwise 
        returns None if no persistance required after analyzing.
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def did_pair_devices(self, credentials, sender, paired_devices):
        """
        *** MANDATORY ***
        Invoked after successful device pairing.

        Receieves,
            credentials     - All persisted user credentials.
            sender          - A dictionary with keys 'channel_template_id', 'owner_id' and 
                        'client_id'.
            paired_devices     - A list of dictionaries with selected device's data

        """
        pass

    @abstractmethod
    def access_check(self, mode, case, credentials, sender):
        """
        *** MANDATORY ***
        Checks if there is access to read from/write to a component.

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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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


        """
        pass

    def polling(self, data):
        """
        Invoked by the manager itself when performing a polling request to manufacturer's API

        Receives,
            data - A dictionary with keys 'channel_id' and 'response' where response is a json object

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
            # logger.debug("Initiated GET"+" - "+url)
            # logger.debug("\n"+json.dumps(params,indent=4,sort_keys=True)+"\n")

            resp = requests.get(url, headers=headers)
            logger.verbose("Received response code[{}]".format(resp.status_code))

            if int(resp.status_code) == 200:
                return resp.json()["channeltemplate_id"]

            else:
                raise Exception("Failed to retrieve channel_template_id")
        except Exception as ex:
            logger.debug("\n{}\n".format(resp))
            logger.trace(str(ex))

    def get_device_id(self, channel_id):
        """
        To retrieve device_id using channel_id

        """
        return db.get_device_id(channel_id)

    def get_channel_id(self, device_id):
        """
        To retrieve channel_id using device_id

        """
        return db.get_channel_id(device_id)

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
        log_table = {
            "0": logger.emergency,
            "1": logger.alert,
            "2": logger.critical,
            "3": logger.error,
            "4": logger.warning,
            "5": logger.notice,
            "6": logger.info,
            "7": logger.debug,
            "8": logger.trace,
            "9": logger.verbose
        }
        log_table[str(level)](message)

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
            logger.error("Renew credentials failed!!! \n"+str(ex))

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

    def start_polling(self):
        """
        If polling is enabled in config file, retrieves conf for polling in implementor
        :return:
        """
        try:
            if settings.config_polling.get('enabled') == True:
                logger.info('**** starting polling ****')
                poll = PollingManager()
                t = Thread(target=poll.worker, args=[self.get_polling_conf()], name="Polling")
                t.start()
            else:
                logger.info('**** polling is not enabled ****')
        except NotImplementedError as e:
            logger.error(e)
        except Exception as e:
            logger.warning(e)



        

