# manager-sdk-python
Internship project of a sdk for python integrations with Muzzley

---

## Setting up the SDK ##

1. Add the sdk as a submodule of your main repository. By default, submodules will add the sub-project into a directory named the same as the repository. You can add a different path at the end of the command, in this case **sdk**.

	    $ git submodule add https://bitbucket.org/muzzley/manager-sdk-python.git sdk

2. Install dependencies from sdk/requirements.txt, (Requires python 3.5.x or later version)

	    $ pip install -r sdk/requirements.txt

---

## Integration with SDK ##

Currently there are two types of managers

* Device Manager
* Application Manager

To integrate with SDK, you need to import the sdk python module in your current path

        import sys
        import os
        sys.path.append(os.path.dirname(__file__) + "/sdk")

> _"sdk" was the path name we used for our submodule_

Following, the manager must implement the Skeleton Class according to your manager type. Given below is a code snippet of a concrete class Implementor class which implements,

 **SkeletonApplication** for Application Managers:

        from base.skeleton_application import SkeletonApplication

        class Implementor(SkeletonApplication):
            # Your Implementation

or **SkeletonDevice** for DeviceManagers:

        from base.skeleton_device import SkeletonDevice

        class Implementor(SkeletonDevice):
            # Your Implementation

Both Skeletons share functions that can be found in sdk/common/skeleton_base.py

---

### Common Abstract methods ###
The abstract methods are invoked by SDK when required and passes it required data to perform specific functions. SDK may except returned data to follow a pre-defined structure or/and type.

##### **start**
Should be always implemented, is executed right after all the configuration is done. Can be used to perform any initial configuration. Does not receive

##### **upstream(mode, case, credentials, sender, data=None)**
Invoked when Muzzley platform intends to communicate with the manager about a read with manufacturer's api to read/update device's information.

* Receives params
	* **mode:**
		* r - read from manufacturer's API
		* w - write to manufacturer's API
	* **case:** A dictionary with 3 key _'channel_id'_, _'component'_ and _'property'_. On Device Managers an additional key is added _'device_id'_,
	* **data:** data if any sent by Muzzley's platform.
	* **credentials:** user credentials from database
	* **sender:** A dictionary with keys _'owner_id'_ and _'client_id'_.

* Expected Response
	* **r** (mode)
        Returns **data** on successful read from manufacturer's API, otherwise returns **None**.
	* **w** (mode)
        Returns **True** on successful write to manufacturer's API, otherwise returns **False**.

##### **downstream(request) :**
Invoked when manufacturer's api intends to communicate with Muzzley's platform to update information.

* Receives
	* **request**: A flask request object received from API webhook.

* Returns a tuple as (case, data),
	* **case**: Expecting a dictionary with keys _'device_id'_, _'component'_ and _'property'_, otherwise if _None_ is returned for case, then data will not be send to muzzley
	* **data**: Any data that has to be send to Muzzley's platform

---

### Device abstract methods ###
Methods only invoked by Device Manager, directly related to Device Manufacturer's functions

##### **auth_requests(self, sender) :**
To find the requests involved in performing authorization with a manufacturer.

* Receives
	*  _sender_      - A dictionary with keys _'channel_template_id'_, _'owner_id'_ and _'client_id'_.

**client_id** should be used to get manufacturer private credentials from config file.
`credentials = settings.config_manufacturer['credentials'][sender['client_id']]`

* Returns a list of dictionaries with the structure,

		[
			{
			    "method" : "<get/post>",
			    "url" : "<manufacturer's authorize API uri and parameters>"
			    "headers" : {}
			},
		...
		]

If the value of headers is {} for empty header, otherwise it follows the structure as of the sample given below.

		"headers" : {
			"Accept": "application/json",
			"Authorization": "Bearer {}".format(credentials.get("app_id"))
		}

Each dictionary in list represent an individual request to be made to manufacturer's API and its position denotes the order of request.

**Example:**

```
location = [
    {
        "method": "get",
        "url": "{}?client_id={}".format(MANUFACTURER_AUTH_URL, credentials.get("app_id")),
        "headers": {
            "Accept": "application/json"
        }
    }
]
```

##### **auth_response(response_data) :**
Used to handle the response received in the final authorization request to manufacturer. Also gathers all essential data required to initiate any request to the manufacturer so the gathered data can be persisted.

* Returns dictionary of required credentials for persistence, otherwise returns *None* if no persistence required after analyzing.

##### **get_devices(sender, credentials) :**
Identify a user's device list from manufacturer to integrate with Muzzley.

* Receives ,
	*  **credentials:** All persisted user credentials.
	*  **sender:** A dictionary with keys '*channel_template_id*', '*owner_id*' and '*client_id*'.

* Returns a list of dictionaries with the following structure, each dictionary in list denotes an user device.

		[
			{
				"content" : "<device name>",
				"id" : "<manufacturer's device ID>",
				"photoUrl" : "<url to device's image in cdn.muzzley.com>"
			},
			...
		]

Device's photo url can be defined as a section on the configuration file, associated to a channel template id.

```
"photo_url": {
	"[CHANNEL_TEMPLATE_ID]": "https://cdn.muzzley.com/things/profiles/manufacturer/name.png"
}
```

##### **did_pair_devices(credentials, sender, paired_devices) :**
Invoked after successful device pairing.

* Receives,
	* **credentials**: All persisted user credentials.
	* **sender**: A dictionary with keys _'channel_template_id'_, _'owner_id'_ and _'client_id'_.
	* **paired_devices**: A list of dictionaries with selected device's data

##### **access_check(mode, case, credentials, sender) :**
Checks if access to read from/write to a component exists.

* Receives,
	* **mode**:
		* r - read from manufacturer's API
		* w - write to manufacturer's API
	* **case**: A dictionary with keys 'device_id','channel_id','component' and 'property'.
	* **credentials**: credentials of user from database
	* **sender**: A dictionary with keys '*owner_id*' and '*client_id*'.

* Returns **updated** valid credentials or **current** ones. Returns **None** if no access.

---

### Common Inbuilt methods ###
The pre-defined methods that belongs to Skeleton class to support implementation of abstract methods.

##### **get_channel_status(channel_id)**
Retrieves channel status data from db using channel_id. **None** is returned if no information is found.

##### **store_channel_status(channel_id, status)**
Store in db status data for a given channel_id. db key has the following format
`status-channels/[CHANNEL_ID]`

##### **store(key, value)**
To store a data in database.
	* _key_: unique identifier corresponding to value.
	* _value_: data to be stored.

##### **retrieve(key)**
Retrieve a data from database with its unique identifier.
	* _key_: unique identifier corresponding to value.

##### **exists(key)**
Check if a data is already present in database with its unique identifier.
	* _key_: unique identifier corresponding to value.

##### **log(message,level)**
Log a message to log file
	* _message_: message to be logged.
	* _level_: denotes the logging priority. The level-priority relation given below,

|priority   |level	|
|-----------|-------|
|emergency	|0		|
|alert		|1		|
|critical	|2		|
|error		|3		|
|warning	|4		|
|notice		|5		|
|info		|6		|
|debug		|7		|
|trace		|8		|
|verbose	|9		|

##### **get_config()**
Returns a dict with the entire data in configuration file.

##### **publisher(case, data)**
Publish data to some topic (case) using mqtt. **io** used to publish the message will always be **iw**
* **case**: a dictionary with keys _'component'_, _'property'_, _'device_id'_ if is a Device Manager or _'channel_id'_ if is an Application Manager.
* **data**: data to be published.

##### **renew_credentials(sender, channel_id, sender, credentials)**
Update credentials in database

* **channel_id**: channel_id of the device.
* **credentials**: a dictionary with data to be updated.
* **sender**: a dictionary with keys _'owner_id'_ and _'client_id'_.

##### **get_type()**
Returns type of the implementor: "device" if is a Device Manager, "application" if is an Application Manager

##### **format_datetime()**
Returned a formatted datetime as timestamp string

---

### Device Inbuilt methods ###

##### **get_channel_template(channel_id)**
Makes an http request to Muzzley's platform to find a _channel_template_id_ for a channel_id. Returns channel_template_id or an empty string if results are not found. Http URI requested
`/channels/[CHANNEL_ID]`

##### **get_device_id(channel_id)**
Retrieve manufacturer device_id from database using channel_id value. If more than 1 result is found, returns first coincidence. Query to db key
`device-channels/[CHANNEL_ID]`

#### **get_channel_id(device_id) :**
Retrieve channel_id using device_id. If more than 1 result is found, returns first coincidence. Query to db key
`channel-devices/[DEVICE_ID]`

---

### Managing Configuration file ##

* The configuration file of your manager must follow the template in *sample-manager-sdk-python.conf* file available in sdk folder.
* All placeholders in configuration file should be replaced with appropriate values.
* **Important :** The *{implementor_path}*  placeholder of sample has to be replaced with the path to the *.py* file of your manager that implements Skeleton class.

---

### How to execute your project ? ##

* To execute your manager, use the command below

		cd sdk
		python run.py path_to_conf

