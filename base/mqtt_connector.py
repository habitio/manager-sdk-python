import json
import logging
import traceback

import paho.mqtt.client as paho

from base.redis_db import db
from base.settings import settings
from base.utils import format_str
from base.constants import DEFAULT_RETRY_WAIT, MANAGER_SCOPE, APPLICATION_SCOPE
from tenacity import retry, wait_fixed

logger = logging.getLogger(__name__)

RC_LIST = {
    0: "Connection successful",
    1: "Connection refused - incorrect protocol version",
    2: "Connection refused - invalid client identifier",
    3: "Connection refused - server unavailable",
    4: "Connection refused - bad username or password",
    5: "Connection refused - not authorised"
}

class MqttConnector():

    def __init__(self):
        logger.debug("Mqtt - Init")
        self.mqtt_client = paho.Client()
        self.mqtt_client.enable_logger()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_subscribe = self.on_subscribe
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect
        self.mqtt_client.on_publish = self.on_publish
        self.implementer = None
        self._topics = []
        self._on_connect_callback = None
        self._on_connect_callback_params = {}

    def on_connect(self, client, userdata, flags, rc):
        try:
            if rc == 0:

                from base.solid import implementer

                self.implementer = implementer

                logger.notice("Mqtt - Connected , result code {}".format(rc))

                topic = "/{api_version}/{mqtt_topic}/{client_id}/channels/#".format(
                    mqtt_topic=settings.mqtt_topic,
                    api_version=settings.api_version,
                    client_id=settings.client_id
                )

                logger.notice("Mqtt - Will subscribe to {}".format(topic))
                self.mqtt_client.subscribe(topic, qos=0)

                if self._on_connect_callback:
                    self._on_connect_callback.__call__(**self._on_connect_callback_params)

            elif 0 < rc < 6:
                raise Exception(RC_LIST[rc])
        except Exception as e:
            logger.error("Mqtt Exception- {}".format(traceback.format_exc(limit=5)))
            exit()

    def on_subscribe(self, client, userdata, mid, granted_qos):
        logger.info("Mqtt - Subscribed , mid({mid}) qos({granted_qos})".format(mid=mid, granted_qos=granted_qos))

    def set_on_connect_callback(self, _func, **kwargs):
        self._on_connect_callback = _func
        self._on_connect_callback_params = kwargs

    def add_topic(self, _topic):

        if _topic not in self._topics:
            self._topics.append(_topic)
            return True

        return False

    def add_topics(self, _topics):

        for _topic in _topics:
            self.add_topic(_topic)

    def on_message_manager(self, client, topic, payload):
        try:

            if "io" in payload and payload["io"] in ("r", "w"):

                if all(k in payload for k in ("on_behalf_of", "sender")):

                    logger.debug(
                        "\n\n\n\n\n\t\t\t\t\t******************* ON MESSAGE ****************************")
                    logger.debug("Mqtt - Received on_message_manager: {}\n{}".format(
                        topic, json.dumps(payload, indent=4, sort_keys=True)))

                    parts = str(topic).split('/')
                    device_id = db.get_device_id(parts[5])

                    if not device_id:
                        logger.warning("Mqtt - channel_id {} not found in database.".format(parts[5]))
                        return

                    case = {
                        "device_id": str(device_id),
                        "channel_id": parts[5],
                        "component": parts[7],
                        "property": parts[9]
                    }

                    data = payload.get("data")

                    sender = {
                        "client_id": payload["sender"],
                        "owner_id": payload["on_behalf_of"]
                    }

                    credentials = db.get_credentials(
                        payload["sender"], payload["on_behalf_of"], case["channel_id"])

                    if not credentials:
                        logger.error("Mqtt - credentials not found in database.")
                        return

                    validated_credentials = self.implementer.access_check(
                        mode='r', case=case, credentials=credentials, sender=sender)

                    if validated_credentials is not None:

                        logger.debug("inside the access check")

                        if payload["io"] == "r":

                            result = self.implementer.upstream(
                                mode='r', case=case, credentials=validated_credentials, sender=sender, data=data)

                            if result is not None:
                                self.publisher(io="ir", data=result, case=case)
                            else:
                                return

                        elif payload["io"] == "w":

                            result = self.implementer.upstream(
                                mode='w', case=case, credentials=validated_credentials, sender=sender, data=data)

                            if result == True:
                                self.publisher(io="iw", data=data, case=case)
                            elif result == False:
                                return

                    else:
                        case["property"] = settings.access_property
                        self.publisher(
                            io="ir", data=settings.access_failed_value, case=case)
                else:

                    logger.error("Mqtt - No 'sender'/'on_behalf_of' in payload")
                    return

            else:
                return

        except Exception as e:
            logger.error("Mqtt - Failed to handle payload. {}".format(traceback.format_exc(limit=5)))

    def on_message_application(self, client, topic, payload):

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

            if settings.implementor_type == MANAGER_SCOPE:
                self.on_message_manager(client, topic, payload)
            elif settings.implementor_type == APPLICATION_SCOPE:
                self.on_message_application(client, topic, payload)

        except Exception as e:
            logger.error("Mqtt - Failed to handle payload. {}".format(traceback.format_exc(limit=5)))

    def on_publish(self, client, userdata, mid):
        logger.debug("\n\n\n\n\n\t\t\t\t\t******************* ON PUBLISH ****************************")
        logger.verbose("Mqtt - Publish acknowledged by broker, mid({}) userdata={}.".format(mid, userdata))

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.error("Mqtt - Unexpected disconnection: {}".format(RC_LIST.get(rc)))
        else:
            logger.error("Mqtt - Expected disconnection.")

    def on_log(self, userdata, level, buf):
        logger.debug("Mqtt - Paho log: {}".format(buf))

    @retry(wait=wait_fixed(DEFAULT_RETRY_WAIT))
    def mqtt_config(self):
        logger.info("Setting up Mqtt connection")
        try:
            parts = settings.block["mqtt_ep"].split(":")
            schema_mqtt = parts[0]

            host = parts[1].replace("//", "")
            port = int(parts[2])

            self.mqtt_client.username_pw_set(
                username=settings.client_id, password=settings.block["access_token"])

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
            try:

                logger.debug("Mqtt - Will start the loop")
                self.mqtt_client.loop_start()

            except Exception as e:
                logger.alert("Mqtt - Failed to listen through loop, {} ".format(traceback.format_exc(limit=5)))
                raise

        except Exception as e:
            logger.emergency("Unexpected error: {}".format(e, traceback.format_exc(limit=5)))
            raise

    def publisher(self, io, data, case=None):
        """
        Receives 3 inputs,
            io    - mode of operation ('ir','iw'). By default, io takes value 'iw'.
            data  - data to be published
            case  - if topic not available, a dictionary used to construct the topic from 
                    keys 'device_id', 'component' and 'property'
        """
        try:
            payload = dict()
            payload["io"] = io

            if data != None:
                payload["data"] = data

            logger.debug(
                "Mqtt - Case {} and settings.api_version={}".format(case, settings.api_version))

            if all(key in case for key in ("device_id", "component", "property")):

                channel_id = db.get_channel_id(case["device_id"])

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
                logger.debug(
                    "Mqtt - Published successfully, result code({}) and mid({}) to topic: {} with payload:{}".format(
                        rc, mid, topic, format_str(payload, is_json=True)))

            else:

                raise Exception(
                    "Mqtt - Failed to publish , result code({})".format(rc))

        except Exception as e:
            logger.alert("Mqtt - Failed to publish , ex {}".format(traceback.format_exc(limit=5)))

    def mqtt_decongif(self):
        try:
            self.mqtt_client.unsubscribe("/{api_version}/managers/{client_id}/channels/#".format(
                api_version=settings.api_version, client_id=settings.client_id))
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            self.mqtt_client.disable_logger()
        except Exception as e:
            logger.error("Mqtt - Failed to de-configure connection {}".format(traceback.format_exc(limit=5)))
            exit()


mqtt = MqttConnector()
