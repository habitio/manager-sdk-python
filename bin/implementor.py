from bin.skeleton import Skeleton
from bin.settings import settings

class Implementor(Skeleton):

    def auth_requests(self):
        """
        Returns a list of dictionaries with the structure,
        
        {
            "method" : "<get/post>"
            "url" : "<manufacturer's authrorize API uri and parameters>"
            "headers" : {}
        }

        If the value of headers is {} for empty header, otherwise it follows the structure as of the 
        sample given below.

        "headers" : {                                             
            "Accept": "application/json", 
            "X-Webview-Authorization": "Bearer {client_secret}" 
        }

        Each dictionary in list respresent an individual request to be made to manufacturer's API and
        its position denotes the order of request.
        """

        response =  [
            {
                "method" : "get",
                "url" : settings.man_login_url+"?redirect_uri={redirect_uri}",
                "headers" : {}
            }
            ,
            {
                "method" : "post",
                "url" : settings.man_token_url+"?redirect_uri={redirect_uri}&code={code}",
                "headers" : {},
                
            }
        ]

        return response
        
        
    def auth_response(self,response_data):
        """
        Receives the response from manufacturer API after authrorization.

        Returns dictionary of required credentials for persistence, otherwise 
        returns None if no persistance required after analyzing.
        """
        return response_data
    
    def get_devices(self,credentials):
        """
        Receives the credentials of user.

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
        data = [
            {
                "content" : "kitchen fridge",
                "id" : "9323u2450nwetu"
            },
            {
                "content" : "microwave",
                "id" : "qiwjfoiasqp34i"
            }
        ]

        return data

    def connect(self,mode,case,credentials,data=None):
        """
        Invoked when Muzzley platform intends to communicate with manufacturer's api
        to read/u
        pdate device's information.

        Receives 3 arguements,
            mode        : 'r' or 'w'
                r - read from manufacturer's API
                w - write to manufacturer's API
            topic       : A dictionary with 3 key 'device_id', 'component' and 'property'.
            data        : data if any sent by Muzzley's platform.
            credentials : credentials of user from database.

        Expected Response,
            'r' - mode
                Returns data on successfull read from manufacturer's API, otherwise
                returns None.
            'w' - mode
                Returns True on successfull write to manufacturer's API, otherwise
                returns False.
        """
        print(mode)
        print(case)
        print(data)

        message = "Hello Bro! Its working"
        if mode == 'r':
            print("In r")
            return message
        else:
            print("In w")
            return True

    def listener(self,message):
        """
        Invoked when manufacturer's api intends to communicate with Muzzley's platform
        to update device's information.

        Returns a tuple with (case, data),
            case - A dictionary with keys 'device_id', 'component' and 'property'
            data - Any data that has to be send to Muzzley's platform
        """
        pass
