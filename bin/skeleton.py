from abc import ABC, abstractmethod
from flask import request
from bin import settings
import requests
import logging

logger = logging.getLogger(__name__)


class Skeleton(ABC):

    @abstractmethod
    def auth_requests(self):
        """
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
            "X-Webview-Authorization": "Bearer {client_secret}" 
        }

        Each dictionary in list respresent an individual request to be made to manufacturer's API and
        its position denotes the order of request.
        """
        pass
        
    @abstractmethod
    def auth_response(self,response_data):
        """
        Receives the response from manufacturer's API after authrorization.

        Returns dictionary of required credentials for persistence, otherwise 
        returns None if no persistance required after analyzing.
        """
        pass
    
    @abstractmethod
    def get_devices(self,credentials):
        """
        Receives : 
            credentials : All persisted user credentials.

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
    def upstream(self,mode,case,credentials,data=None):
        """
        Invoked when Muzzley platform intends to communicate with manufacturer's api
        to read/u
        pdate device's information.

        Receives:
            mode        - 'r' or 'w'
                r - read from manufacturer's API
                w - write to manufacturer's API
            topic       - A dictionary with 3 key 'device_id','channel_id','component' and 'property'.
            data        - data if any sent by Muzzley's platform.
            credentials - credentials of user from database

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
        Invoked when manufacturer's api intends to communicate with Muzzley's platform
        to update device's information.
        
        Receives :
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

        url = settings.api_version_full+"/managers/self/channels"
        headers = {
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        } 
        params = {
            "channel_id" : channel_id
        }

        try :
            logger.debug("Initiated GET"+" - "+url)
            logger.verbose("\n"+json.dumps(params,indent=4,sort_keys=True)+"\n")

            resp = requests.get(url,headers=headers,params=params)

            logger.verbose("Received response code["+str(resp.status_code)+"]") 
            if int(resp.status_code) == 200:
                logger.verbose("\n"+json.dumps(resp.json(),indent=4,sort_keys=True)+"\n")
                return resp.json()["channel_template_id"]
            else:
                raise Exception("Failed to retrieve channel_template_id")
        except Exception as ex:
            logger.debug("\n"+json.dumps(resp.json(),indent=4,sort_keys=True)+"\n")
            logger.trace(str(ex))
        
        