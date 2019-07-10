# manager-sdk-python
Internship project of a sdk for python integrations with Muzzley

---

## Setting up the SDK ##

1. Add the sdk as a submodule of your main repository. By default, submodules will add the sub-project into a directory named the same as the repository. You can add a different path at the end of the command, in this case **sdk**.

	    $ git submodule add git@bitbucket.org:muzzley/manager-sdk-python.git sdk

2. Install dependencies from sdk/requirements.txt, (Requires python 3.5.x or later version)

	    $ pip install -r sdk/requirements.txt

> _systemd-python only works under linux os_
---

## Integration with SDK ##

Currently there are two types of managers

* Device Manager
* Application Manager

To integrate with SDK, you need to import the sdk python module in your current path

        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), 'sdk'))

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
	* **case**: Expecting a dictionary with keys _'device_id'_ or _'channel_id'_ (according to the request data received), _'component'_ and _'property'_, otherwise if _None_ is returned for case, then data will not be send to muzzley
	* **data**: Any data that has to be send to Muzzley's platform

---

### Device abstract methods ###
Methods only invoked by Device Manager, directly related to Device Manufacturer's functions

##### **auth_requests(self, sender) :**
To find the requests involved in performing authorization with a manufacturer.

* Receives
	*  _sender_      - A dictionary with keys _'channel_template_id'_, _'owner_id'_ and _'client_id'_.

**client_id** should be used to get manufacturer private credentials from config file.

```
from base import settings
credentials = settings.config_manufacturer['credentials'][sender['client_id']]
```

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

**Example:**

        {
            'access_token': '{access_token}',
            'refresh_token': '{refresh_token}',
            'token_type': '{token_type}',
            'expires_in': {expires_in},
            'expiration_date': {expiration_date},
            'client_id': '{client_id}'
        }

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

##### **get_refresh_token_conf()**
When Token Refresh configuration is enabled, manager should implement this additional method.

* Returns a python dictionary with 'url' and 'headers' (if required) keys

##### **get_polling_conf()**
If Polling configuration is enabled, manager should implement this method

* Returns a python dictionary with 'url', 'method', 'params', 'data' key. These will be used as params on a "requests.request" object to perform polling to manufacturer's API.

##### **polling(data)**
This method is invoked by a polling thread if enabled.

- Receives a data dictionary with 'response', 'channel_id' and 'credentials'.
    - response: polling response as a json object.
    - channel_id: device channel_id which performed the polling request.
    - credentials: manufacturer credentials used during the polling request. This also can be use if a new request needs to be done.

#### **after_refresh(after_refresh)**
Invoked when successfully refreshing a token, either by a token refresher process and ideally should be included after every token refresh call within the manager.

- Receives a data dictionary with keys 'channel_id' and 'new_credentials'

---

### Common Inbuilt methods ###
The pre-defined methods that belongs to Skeleton class to support implementation of abstract methods.

##### **get_channel_status(channel_id)**
Retrieves channel status data from db using channel_id. **None** is returned if no information is found.

##### **store_channel_status(channel_id, status)**
Store in db status data for a given channel_id. db key has the following format
```
status-channels/[CHANNEL_ID]
```

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

##### **get_channeltemplate_data(channeltemplate_id)**
Retrieves channel template data given an channeltemplate_id, returns an empty dict if not data is found.

##### **get_latest_property_value(channel_id, component, property)**
Return the latest value received by the platform for a given channel_id/component/property, an empty dict is returned if no data if found.

##### **get_params(channel_id, url, credentials)**
Create params dict to be sent in token_refresher request.

Return formated url (str) and params (dict).

##### **get_headers(self, credentials, headers)**
Create headers dict to be sent in token_refresher request.

Return headers (dict).

---

### Device Inbuilt methods ###

##### **get_channel_template(channel_id)**
Makes an http request to Muzzley's platform to find a _channel_template_id_ for a channel_id. Returns channel_template_id or an empty string if results are not found. Http URI requested
```
/channels/[CHANNEL_ID]
```

##### **get_device_id(channel_id)**
Retrieve manufacturer device_id from database using channel_id value. If more than 1 result is found, returns first coincidence. Query to db key
```
device-channels/[CHANNEL_ID]
```

##### **get_channel_id(device_id)**
Retrieve channel_id using device_id. If more than 1 result is found, returns first coincidence. Query to db key
```
channel-devices/[DEVICE_ID]
```

---

### Managing Configuration file ##

* The configuration file of your manager must follow the template in _sample-manager-sdk-python.conf_ for Device Managers and _sample-application-sdk-python.conf_ for Application Managers file available in sdk folder.
* All placeholders in configuration file should be replaced with appropriate values.
* **Important :** The *{implementor_path}*  placeholder of sample has to be replaced with the path to the *.py* file of your manager that implements Skeleton class.

#### Device Manager configurations

##### manufacturer

* application_id: Application unique ID given by Muzzley
* manufacturer_app_id: Usually known as client_id or api_key (Oauth2)
* manufacturer_app_secret: Also known as client_secret, sometimes this could be optional

##### channel_templates
This can be used to easily identify with a namespace what type of device correspond to a channel_id

```
"channel_templates": {
    "thermostat": "0000-1111-0000-1111"
}
```

##### photo_url
In this section a device photo url can be define by configuration, this later can be use by list_devices on pairing process. Image url should be under muzzley cdn.

```
"photo_url": {
    "0000-1111-0000-1111"": "https://cdn.muzzley.com/things/profiles/[MANUFACTURER_NAMESPACE]/[IMAGE_NAME]"
}
```

##### polling (optional)
This section is optional, when polling needs to be enabled.  Http polling requests will be made channel by channel. Channels are found by querying all devices under `channel-devices/[CHANNEL_ID]` keys.

* enabled: boolean value (true/false)
* interval_seconds: Is the period of time where a polling thread will perform requests to manufacturer's api. If not defined, default value is `DEFAULT_POLLING_INTERVAL` (constants.py).
* rate_limit: Is the limited amount of request by second. Useful to follow possible restrictions on manufacturer's api. If not defined, default value is `DEFAULT_RATE_LIMIT` (constants.py)

*see polling section in [sample configuration file](sample-manager-sdk-python.conf)*

##### token_refresher (optional)
This section is optional, when an automatic token refresh process needs to be enabled. Http refresh token requests will be made by owner credentials. Credentials are found by querying all owners credentials of all their channels `credential-owners/*/channels/*`

* enabled: boolean value (true/false)
* interval_seconds: Is the period of time where a token_refresher thread will perform requests to manufacturer's api. If not defined, default value is `DEFAULT_REFRESH_INTERVAL` (constants.py).
* rate_limit: Is the limited amount of request by second. Useful to follow possible restrictions on manufacturer's api. If not defined, default value is `DEFAULT_RATE_LIMIT` (constants.py)
* before_expires_seconds: This is the time margin before an access token expires. Leaving enough space to the refresh token process to successful execute. This means, if an access_token has an expiration time of 1 hour and before_expires_seconds is defined by 300 seconds. This token will try to refresh after 5 minutes before it expires. If not defined, default value is `DEFAULT_BEFORE_EXPIRES` (constants.py).
* update_owners: boolean value (true/false). Default False. If enabled while refreshing a Token will also try to find all owners associated to the current refreshing channel, and all channels associated with the current refreshing owner, and update their credentials as well if they have the same refresh_token.

*see token_refresher section in [sample configuration file](sample-manager-sdk-python.conf)*

*see token_refresher section in [sample configuration file](sample-manager-sdk-python.conf)*

#### Application Manager configurations

##### services

##### usecases

---

### Access Values

- ACCESS_NO_POWER = 'no_power'
- ACCESS_DISCONNECTED = 'disconnected'
- ACCESS_UNREACHABLE_VALUE = 'unreachable'
- ACCESS_REMOTE_CONTROL_DISABLED = 'remote_control_disabled'
- ACCESS_PERMISSION_REVOKED = 'permission_revoked'
- ACCESS_SERVICE_ERROR_VALUE = 'service_error'  # this retry reading the property
- ACCESS_UNAUTHORIZED_VALUE = 'unauthorized'  # this shows a blue
- ACCESS_API_UNREACHABLE = 'api_unreachable'
- ACCESS_NOK_VALUE = 'nok'
- ACCESS_CONNECTED = 'connected'
- ACCESS_OK_VALUE = 'ok'

---

### How to execute your project ? ##

* To execute your manager, use the command below

		cd sdk
		python run.py path_to_conf

