sys.path.append(os.path.dirname(__file__) + "/sdk")
from base.skeleton import Skeleton

class Implementor(Skeleton):

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
        
        response =  [
            {
                "method" : "get",
                "url" : "<some url>",
                "headers" : {}
            }
            ,
            {
                "method" : "post",
                "url" : "<some url>",
                "headers" : {},
                
            }
        ]

        return response
        
        
    def auth_response(self,response_data):
        """
        Receives the response from manufacturer's API after authrorization.

        Returns dictionary of required credentials for persistence, otherwise 
        returns None if no persistance required after analyzing.
        """
        return response_data
    
    def get_devices(self,sender,credentials):
        """
        *** MANDATORY ***
        Receives : 
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

    def upstream(self,mode,case,credentials,data=None):
        """
        *** MANDATORY ***
        Invoked when Muzzley platform intends to communicate with manufacturer's api
        to read/u
        pdate device's information.

        Receives:
            mode        - 'r' or 'w'
                r - read from manufacturer's API
                w - write to manufacturer's API
            case       - A dictionary with 3 key 'device_id','channel_id','component' and 'property'.
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
        print(mode)
        print(case)
        print(data)

        message = "Its working"
        if mode == 'r':
            print("In r")
            return message
        else:
            print("In w")
            return True

    def downstream(self,message):
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
