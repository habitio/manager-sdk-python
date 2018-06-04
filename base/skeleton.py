from abc import ABC, abstractmethod
from flask import request
from base.settings import settings
from base.redis_db import db
import requests
import logging
# from base.paho_mqtt import publisher
from base.mqtt_connector import mqtt
import json

logger = logging.getLogger(__name__)


class Skeleton(ABC):

    @abstractmethod
    def auth_requests(self):
        """
        *** MANDATORY ***
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
    def auth_response(self,response_data):
        """
        *** MANDATORY ***
        Receives the response from manufacturer's API after authrorization.

        Returns dictionary of required credentials for persistence, otherwise 
        returns None if no persistance required after analyzing.
        """
        pass
    
    @abstractmethod
    def get_devices(self,sender,credentials):
        """
        *** MANDATORY ***
        Receives,
            credentials - All persisted user credentials.
            sender      - A dictionary with keys 'channel_template_id', 'owner_id' and 
                        'client_id'.

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
    def did_pair_devices(self,credentials,sender,paired_devices):
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
    def access_check(self,mode,case,credentials,sender):
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
    def upstream(self,mode,case,credentials,sender,data=None):
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
    def downstream(self,request):
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
    
    def get_channel_template(self,channel_id):
        """
        Input : 
            channel_id - channel_id of the device.

        Returns channel_template_id

        """

        url = settings.api_server_full+"/channels/"+str(channel_id)
        headers = {
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        } 
        try :
            # logger.debug("Initiated GET"+" - "+url)
            # logger.debug("\n"+json.dumps(params,indent=4,sort_keys=True)+"\n")

            resp = requests.get(url,headers=headers)

            logger.verbose("Received response code["+str(resp.status_code)+"]") 
            if int(resp.status_code) == 200:
                # logger.debug("\n"+json.dumps(resp.json(),indent=4,sort_keys=True)+"\n")
                return resp.json()["channeltemplate_id"]
                
            else:
                raise Exception("Failed to retrieve channel_template_id")
        except Exception as ex:
            logger.debug("\n"+json.dumps(resp.json(),indent=4,sort_keys=True)+"\n")
            logger.trace(str(ex))
    
    def get_device_id(self,channel_id):
        """
        To retrieve device_id using channel_id

        """
        return db.get_device_id(channel_id)


    def get_channel_id(self,device_id):
        """
        To retrieve channel_id using device_id

        """
        return db.get_channel_id(device_id)

    def store(self,key,value):
        """
        To store a value to database with a unique identifier called key

        """
        db.set_key(key,value)

    def retrieve(self,key):
        """
        To retireve a value from database with its unique identifier, key.

        """
        return db.get_key(key)

    def exists(self,key):
        """
        To check if a key is already present in database.

        """
        return db.has_key(key)

    def log(self,message,level):
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
        log_table =  {
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

    def publisher(self,case,data):
        """
        To make an mqtt publish
            case - a dictionary with keys  'device_id', 'component' and 'property'
            data - data to be published
        """
        logger.debug("Will publisher to mqtt")
        mqtt.publisher(io="iw",data=data,case=case)
        
    def renew_credentials(self,channel_id,sender,credentials,rub=False):
        """
        To update credentials in database
            channel_id - channel_id of the device.
            credentials - a dictionary with data to be updated. 
            sender      - a dictionary with keys 'owner_id' and 
                        'client_id'.
            rub         - flag variable , 'False' by default.
                            if 'True'  - overwrites entire credentials.
                            if 'False' - overwrites specific data in credentials.
        """
        try:
            key = "/".join([sender["owner_id"],channel_id]) 
            if self.exists(key):
                original = self.retrieve(key)
            elif self.exists(sender["owner_id"]):
                original = self.retrieve(sender["owner_id"])
            else : 
                logger.warning("Original credentials not found : "+str(key))

            if rub:
                self.store(key,credentials)
            else:
                if not original is None:
                    original.update(credentials)
                    self.store(key,original)
                    logger.debug("Credentials successfully renewed : "+str(key)+" !")
                else:
                    raise Exception("Renew credentials failed")

        except Exception as ex:
            logger.error("Renew credentials failed!!! \n"+str(ex))

