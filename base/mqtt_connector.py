import os
import json
import traceback
import paho.mqtt.client as paho
from tenacity import retry, wait_fixed

from base import settings
from base.redis_db import get_redis
from base.utils import format_str
from base.constants import *
from base.exceptions import *

logger = logging.getLogger(__name__)

RC_LIST = {
    0: "Connection successful",
    1: "Connection refused - incorrect protocol version",
    2: "Connection refused - invalid client identifier",
    3: "Connection refused - server unavailable",
    4: "Connection refused - bad username or password",
    5: "Connection refused - not authorised"
}

class MqttConnector:

    def __init__(self, client_id=None, access_token=None, implementer=None, queue=None, queue_pub=None, subscribe=True, **kwargs):
        logger.debug("Mqtt - Init")
        self.mqtt_client = paho.Client()
        self.mqtt_client.enable_logger()

        self.mqtt_client.on_connect = self.on_connect if 'on_connect' not in kwargs else kwargs['on_connect']
        self.mqtt_client.on_subscribe = self.on_subscribe if 'on_subscribe' not in kwargs else kwargs['on_subscribe']
        self.mqtt_client.on_message = self.on_message if 'on_message' not in kwargs else kwargs['on_message']
        self.mqtt_client.on_disconnect = self.on_disconnect if 'on_disconnect' not in kwargs else kwargs['on_disconnect']
        self.mqtt_client.on_publish = self.on_publish if 'on_publish' not in kwargs else kwargs['on_publish']
        self._topics = []
        self._on_connect_callback = None
        self._on_connect_callback_params = {}

        self.client_id = client_id if client_id else settings.client_id
        self.access_token = access_token if access_token else settings.block["access_token"]

        self.db = get_redis()
        self.implementer = implementer
        self.queue = queue
        self.queue_pub = queue_pub
        self.subscribe = subscribe


    def on_connect(self, client, userdata, flags, rc):
        try:
            if rc == 0:
                logger.debug("Mqtt - Connected , result code {}".format(rc))

                topic = "/{api_version}/{mqtt_topic}/{client_id}/channels/#".format(
                    mqtt_topic=settings.mqtt_topic,
                    api_version=settings.api_version,
                    client_id=settings.client_id
                )

                if self.subscribe:

                    logger.notice("Mqtt - Will subscribe to {}".format(topic))
                    self.mqtt_client.subscribe(topic, qos=0)

                    if self._on_connect_callback:
                        self._on_connect_callback.__call__(**self._on_connect_callback_params)

            elif 0 < rc < 6:
                raise Exception(RC_LIST[rc])
        except Exception as e:
            logger.error("Mqtt Exception- {}".format(traceback.format_exc(limit=5)))
            os._exit(1)

    def on_subscribe(self, client, userdata, mid, granted_qos):
        logger.info("Mqtt - Subscribed , mid({mid}) qos({granted_qos})".format(mid=mid, granted_qos=granted_qos))

    def set_on_connect_callback(self, _func, **kwargs):
        self._on_connect_callback = _func
        self._on_connect_callback_params = kwargs

    def on_message_manager(self, topic, payload):
        try:
            parts = str(topic).split('/')
            channel_id = parts[5]
            component = parts[7]
            property = parts[9]

            case = {
                "channel_id": channel_id,
                "component": component,
                "property": property
            }
            access_failed_value = None

            if "io" in payload and payload["io"] in ("r", "w"):

                mode = payload["io"]

                if all(k in payload for k in ("on_behalf_of", "sender")):

                    logger.debug(
                        "\n\n\n\n\n\t\t\t\t\t******************* ON MESSAGE ****************************")
                    logger.debug("Mqtt - Received on_message_manager: {}\n{}".format(
                        topic, json.dumps(payload, indent=4, sort_keys=True)))

                    device_id = self.db.get_device_id(parts[5])

                    if not device_id:
                        if property == HEARTBEAT_PROP:
                            return
                        logger.warning("Mqtt - channel_id {} not found in database.".format(parts[5]))
                        case["device_id"] = ""
                        access_failed_value = ACCESS_SERVICE_ERROR_VALUE
                        raise NoAccessDeviceException

                    case["device_id"] = str(device_id)

                    data = payload.get("data")

                    sender = {
                        "client_id": payload["sender"],
                        "owner_id": payload["on_behalf_of"]
                    }

                    credentials, credential_key = self.db.get_credentials(
                        payload["sender"], payload["on_behalf_of"], case["channel_id"], with_key=True)

                    sender["key"] = credential_key

                    if not credentials:
                        logger.error("Mqtt - credentials not found in database.")
                        return

                    validated_credentials = self.implementer.access_check(
                        mode='r', case=case, credentials=credentials, sender=sender)

                    if validated_credentials is not None:

                        logger.debug("inside the access check")

                        result = self.implementer.upstream(
                            mode=mode, case=case, credentials=validated_credentials, sender=sender, data=data)

                        if mode == "r":

                            if result is not None :
                                self.queue_pub.put({"io": "ir", "data": result, "case": case})
                            else:
                                return

                        elif payload["io"] == "w":

                            if result == True:
                                self.queue_pub.put({"io": "iw", "data": data, "case": case})
                            elif result == False:
                                return

                    else:
                        access_failed_value = ACCESS_UNAUTHORIZED_VALUE
                        raise InvalidAccessCredentialsException

                else:

                    logger.error("Mqtt - No 'sender'/'on_behalf_of' in payload")
                    return

            else:
                return
        except (NoAccessDeviceException, InvalidAccessCredentialsException) as e:
            case["property"] = settings.access_property
            if access_failed_value is None:
                access_failed_value = ACCESS_UNAUTHORIZED_VALUE
            logger.error('1. Access exception raised: {}, sending value: {}'.format(e, access_failed_value))

            self.queue_pub.put({"io": "ir", "data": access_failed_value, "case": case})
        except UnauthorizedException as e:
            case["property"] = settings.access_property
            logger.error('2. Access exception raised: {}, sending value: {}'.format(e, ACCESS_UNAUTHORIZED_VALUE))

            self.queue_pub.put({"io": "ir", "data": ACCESS_UNAUTHORIZED_VALUE, "case": case})
        except RemoteControlDisabledException as e:
            case["property"] = settings.access_property
            logger.error('3. Access exception raised: {}, sending value: {}'.format(e, ACCESS_REMOTE_CONTROL_DISABLED))

            self.queue_pub.put({"io": "ir", "data": ACCESS_REMOTE_CONTROL_DISABLED, "case": case})
        except PermissionRevokedException as e:
            case["property"] = settings.access_property
            logger.error('4. Access exception raised: {}, sending value: {}'.format(e, ACCESS_PERMISSION_REVOKED))

            self.queue_pub.put({"io": "ir", "data": ACCESS_PERMISSION_REVOKED, "case": case})
        except ApiConnectionErrorException as e:
            case["property"] = settings.access_property
            logger.error('5. Access exception raised: {}, sending value: {}'.format(e, ACCESS_API_UNREACHABLE))

            self.queue_pub.put({"io": "ir", "data": ACCESS_API_UNREACHABLE, "case": case})
        except Exception as e:
            logger.error("6. Mqtt - Failed to handle payload. {}".format(traceback.format_exc(limit=5)))

    def on_message_application(self, topic, payload):

        if "io" in payload and payload["io"] in ("r", "w"):

            parts = str(topic).split('/')
            case = {
                "channel_id": parts[5],
                "component": parts[7],
                "property": parts[9]
            }

            data = payload.get("data")

            sender = {
                "client_id": payload.get("sender"),
                "owner_id": payload.get('on_behalf_of')
            }

            self.implementer.upstream(
                mode=payload["io"],
                case=case,
                credentials={},
                sender=sender,
                data=data
            )

    def on_message(self, client, userdata, msg):

        try:

            topic = msg.topic
            payload = json.loads(msg.payload.decode("utf-8"))

            logger.debug("\n\n\n\n\n\t\t\t\t\t******************* ON MESSAGE ****************************")
            logger.debug("Mqtt - Received on_message {topic} {payload}".format(
                topic=topic, payload=format_str(payload, is_json=True)))

            data = {
                "type": settings.implementor_type,
                "topic": topic,
                "payload": payload
            }
            if "io" in payload and payload["io"] in ("r", "w"):
                self.queue.put(data)


        except Exception as e:
            logger.error("Mqtt - Failed to handle payload. {}".format(traceback.format_exc(limit=5)))

    def on_publish(self, client, userdata, mid):
        logger.debug("\n\n\n\n\n\t\t\t\t\t******************* ON PUBLISH ****************************")
        logger.verbose("Mqtt - Publish acknowledged by broker, mid({}) userdata={}.".format(mid, userdata))

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.error("Mqtt - Unexpected disconnection: {}".format(RC_LIST.get(rc)))
            self.mqtt_config()
        else:
            logger.error("Mqtt - Expected disconnection.")

    def on_log(self, userdata, level, buf):
        logger.debug("Mqtt - Paho log: {}".format(buf))

    def reconfig(self):
        try:
            self.mqtt_client.username_pw_set(username=self.client_id, password=self.access_token)
        except Exception as e:
            logger.error("Unexpected error reconfig: {}".format(e))
            raise

    @retry(wait=wait_fixed(DEFAULT_RETRY_WAIT))
    def mqtt_config(self):
        logger.info("Setting up Mqtt connection")
        try:
            parts = settings.block["mqtt_ep"].split(":")
            schema_mqtt = parts[0]

            host = parts[1].replace("//", "")
            port = int(parts[2])

            self.mqtt_client.username_pw_set(username=self.client_id, password=self.access_token)

            try:

                logger.debug("mqtt_client._ssl = {}".format(self.mqtt_client._ssl))

                if not self.mqtt_client._ssl and schema_mqtt == "mqtts":
                    logger.debug("Will set tls")
                    self.mqtt_client.tls_set(ca_certs=settings.cert_path)

            except Exception as e:
                logger.alert("Mqtt - Failed to authenticate SSL certificate, {}".format(traceback.format_exc(limit=5)))
                raise

            self.mqtt_client.connect(host, port)
            logger.debug( "Mqtt - Did start connect w/ host:{} and port:{}".format(host, port))

        except Exception as e:
            logger.emergency("Unexpected error: {}".format(e, traceback.format_exc(limit=5)))
            raise

    def publisher(self, io, data, case=None):
        """
        Receives 3 inputs,
            io    - mode of operation ('ir','iw'). By default, io takes value 'iw'.
            data  - data to be published
            case  - if topic not available, a dictionary used to construct the topic from 
                    keys 'device_id' or 'channel_id', 'component' and 'property'
        """
        try:
            self.reconfig()

            payload = dict()
            payload["io"] = io

            if data != None:
                payload["data"] = data

            logger.debug(
                "Mqtt - Case {} and settings.api_version={} payload={}".format(case, settings.api_version, payload))
            
            if all(key in case for key in ("device_id", "component", "property")) or all(key in case for key in ("channel_id", "component", "property")):

                channel_id = case["channel_id"] if "channel_id" in case else self.db.get_channel_id(case["device_id"])

                if channel_id is None:
                    logger.warning("Mqtt - No channel id found for this device")
                    return

                topic = "/{api_version}/channels/{channel_id}/components/{component}/properties/{property}/value".format(
                    api_version=settings.api_version,
                    channel_id=channel_id,
                    component=case["component"],
                    property=case["property"]
                )
            else:

                logger.warning("Mqtt - Invalid arguments provided to publisher.")
                raise Exception

            (rc, mid) = self.mqtt_client.publish(
                topic=topic, payload=json.dumps(payload))

            if rc == 0:
                logger.info(
                    "Mqtt - Published successfully, result code({}) and mid({}) to topic: {} with payload:{}".format(
                        rc, mid, topic, format_str(payload, is_json=True)))

            else:

                raise Exception(
                    "Mqtt - Failed to publish , result code({})".format(rc))

        except Exception as e:
            logger.alert("Mqtt - Failed to publish , ex {}".format(e))

    def mqtt_decongif(self):
        try:
            self.mqtt_client.unsubscribe("/{api_version}/managers/{client_id}/channels/#".format(
                api_version=settings.api_version, client_id=settings.client_id))
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            self.mqtt_client.disable_logger()
        except Exception as e:
            logger.error("Mqtt - Failed to de-configure connection {}".format(traceback.format_exc(limit=5)))
            os._exit(1)
