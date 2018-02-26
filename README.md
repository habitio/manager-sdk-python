---

##Setting up the SDK##

1. Clone the SDK into a directory named *sdk* in you project folder from,

	    git@bitbucket.org:muzzley/manager-fake-contained.git

2. Install the dependencies of SDK from sdk/requiremnts.txt using,

	    pip install -r sdk/requirements.txt
	    
3. Requires python 3.5.x or later version to execute the manager with SDK.

---

##Intergration with SDK##

* To integrate with SDK, your manager must implement the abstract class Skeleton in sdk/base/skeleton.py. 

    Given below is a code snippet of a concrete class Implementor class which implements Skeleton, 

        sys.path.append(os.path.dirname(__file__) + "/sdk")
        from base.skeleton import Skeleton

        class Implementor(Skeleton):
            #Your Implementation

* Your concrete class has to implement every abstract methods of Skeleton.
	
	
		Tip: A sample implementation of Skeleton has been provided in sdk/base/sample-implementor.py


###Abstract methods###
The abstract methods are invoked by SDK when required and passes it required data to perform specific functions. SDK may except returned data to follow a pre-defined structure or/and type.



>####**auth_requests() :**


* To find the requests involved in performing authorization with a manufacturer.

* Returns a list of dictionaries with the structure,

		[
			{
			    "method" : "<get/post>",
			    "url" : "<manufacturer's authrorize API uri and parameters>"
			    "headers" : {}
			},
		...
		] 
		
* If the value of headers is {} for empty header, otherwise it follows the structure as of the sample given below.

		"headers" : {
			"Accept": "application/json", 
			"X-Webview-Authorization": "Bearer {client_secret}" 
		}

* Each dictionary in list respresent an individual request to be made to manufacturer's API and its position denotes the order of request.

---

>####**auth_response(response_data) :**


* To handle the response received in the final authorization request to manufacturer.

* Also gathers all essential data required to initiate any request to manufacturer so the gathered data can be persisted.

* Returns dictionary of required credentials for persistence, otherwise returns *None* if no persistance required after analyzing.

---
>####**get_devices(sender,credentials) :**

* To identify a user's device list from manufacturer to integrate with Muzzley.
* Receives , 
	*  _credentials_  - All persisted user credentials.
	*  _sender_      - A dictionary with keys '*channel_template_id*', '*owner_id*' and '*client_id*'.

* Returns a list of dictionaries with the following structure ,

		[
			{
				"content" : "<device name>",
				"id" : "<manufacturer's device ID>",
				"photoUrl" : "<url to device's image in cdn.muzzley.com>"
			},
			...
		]

* Each dictionary in list denotes a device of user.


---
>####**did_pair_devices(credentials,sender,paired_devices) :**

* Invoked after successful device pairing.

* Receives,
	* *credentials*     - All persisted user credentials.
	* *sender*          - A dictionary with keys '*channel_template_id*', '*owner_id*' and '*client_id*'.
	* *paired_devices*     - A list of dictionaries with selected device's data

---
>####**access_check(mode,case,credentials,sender) :**

* Checks if access to read from/write to a component exists.

* Receives,
	* *mode*        - 'r' or 'w'
		* r - read from manufacturer's API
		* w - write to manufacturer's API
	* *case*       - A dictionary with keys 'device_id','channel_id','component' and 'property'.
	* *credentials* - credentials of user from database
	* *sender*      - A dictionary with keys '*owner_id*' and '*client_id*'.

* Returns *False* if no access, otherswise returns *True*.

---
>####**upstream(mode,case,credentials,sender,data=None) :**

* Invoked when Muzzley platform intends to communicate with manufacturer's api to read/update device's information.

* Receives,
	* *mode*        - 'r' or 'w'
		* r - read from manufacturer's API
		* w - write to manufacturer's API
	* *case*       - A dictionary with 3 key '*device_id*','*channel_id*','*component*' and '*property*'.
	* *data*        - data if any sent by Muzzley's platform.
	* *credentials* - credentials of user from database
	* *sender*      - A dictionary with keys '*owner_id*' and '*client_id*'.

* Expected Response,
	* 'r' - mode
        Returns data on successfull read from manufacturer's API, otherwise returns *None*.
	* 'w' - mode
        Returns *True* on successfull write to manufacturer's API, otherwise returns *False*.

---
>####**downstream(request) :**

* Invoked when manufacturer's api intends to communicate with Muzzley's platform to update device's information.

* Receives ,
	* *request* - A flask.request object received from manufacturer's API.

* Returns a tuple as (case, data),
	* *case* - Expecting a dictionary with keys '*device_id*', '*component*' and '*property*', otherwise if *None* is returned for case, then data will not be send to muzzley
	* *data* - Any data that has to be send to Muzzley's platform


###Inbuilt methods###
The pre-defined methods that belongs to Skeleton class to support implmentation of abstract methods.

>####**get_channel_template(channel_id) :**

* Makes request to Muzzley's platform to find channel_template_id with channel_id.
 	* *channel_id* - identfier of channel associated to a device.
 	
* Returns channel_template_id.

---
>####**get_device_id(channel_id) :**

* To retrieve device_id using channel_id
    * *channel_id* - identfier of channel associated to a device.
 	
* Returns device_id.

---
>####**get_channel_id(device_id) :**

* To retrieve channel_id using device_id
    * *device_id* - unique identfier of device assigned by manufacturer.
 	
* Returns channel_id.

---
>####**store(key,value) :**

* To store a data in database.
	* *key* - unique indentifier corresponsing to value.
	* *value* - data to be stored.

---
>####**retrieve(key) :**

* To retireve a data from database with its unique identifier.
	* *key* - unique indentifier corresponsing to value.

---
>####**exists(key) :**

* To check if a data is already present in database with its unique identifier.
	* *key* - unique indentifier corresponsing to value.
	
---
>####**log(message,level) :**

* To log a message to log file 
	* *message* - message to be logged.
	* *level*   - denotes the logging priority. The level-priority relation given below,

		|priority    	|level	|
		|-----------------	|------------|
		|emergency	|0		|
		|alert		|1		|
		|critical		|2		|
		|error		|3		|
		|warning		|4		|
		|notice		|5		|
		|info		|6		|
		|debug		|7		|
		|trace		|8		|
		|verbose		|9		|

---
>####**get_config() :**

* Returns the entire data in configuration file.

---
>####**publisher(case,data) :**

* To publish data to some topic using mqtt.
	* *case* - a dictionary with keys  '*device_id*', '*component*' and '*property*'.
	* *data* - data to be published.
---
>####**renew_credentials(sender,credentials,rub=False):**

* To update credentials in database
    * *channel_id* - channel_id of the device.
    * *credentials* - a dictionary with data to be updated. 
    * *sender*      - a dictionary with keys '*owner_id*' and '*client_id*'.
    * *rub*         - flag variable , 'False' by default.
        * if '*True*'  - overwrites entire credentials.
        * if '*False*' - overwrites specific data in credentials.

---
###Managing Configuration file##

* The configuration file of your manager must follow the template in *sample-manager-sdk-python.conf* file available in sdk folder. 
* All placeholders in configuration file should be replaced with appropriate values.
* **Important :** The *{implementor_path}*  placeholder of sample has to be replaced with the path to the *.py* file of your manager that implements Skeleton class.

---

###How to execute your project ?##

* To execute your manager, use the command below

		cd sdk
		python run.py path_to_conf


---
