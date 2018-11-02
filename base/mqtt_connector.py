import json
import logging

import paho.mqtt.client as paho

from base.redis_db import db
from base.settings import settings
from base.utils import format_str

logger = logging.getLogger(__name__)


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

    def on_connect(self, client, userdata, flags, rc):
        try:
            if rc == 0:
                logger.notice("Mqtt - Connected , result code {}".format(rc))
                topic = "/{api_version}/managers/{client_id}/channels/#".format(
                    api_version=settings.api_version, client_id=settings.client_id
                )
                logger.notice("Mqtt - Will subscribe to {}".format(topic))

                self.mqtt_client.subscribe(topic, qos=0)
            elif rc > 0 and rc < 6:
                rc_list = {
                    0: "Connection successful",
                    1: "Connection refused - incorrect protocol version",
                    2: "Connection refused - invalid client identifier",
                    3: "Connection refused - server unavailable",
                    4: "Connection refused - bad username or password",
                    5: "Connection refused - not authorised",
                }
                raise Exception(rc_list[rc])
        except Exception as ex:
            logger.error("Mqtt - {}".format(ex))
            exit()

    def on_subscribe(self, client, userdata, mid, granted_qos):
        logger.info("Mqtt - Subscribed , mid({mid}) qos({granted_qos})".format(mid=mid, granted_qos=granted_qos))

    def on_message(self, client, userdata, msg):
        try:
            from base.solid import implementer

            topic = msg.topic
            payload = json.loads(msg.payload.decode("utf-8"))

            if "io" in payload and payload["io"] in ("r", "w"):
                if all(k in payload for k in ("on_behalf_of", "sender")):

                    logger.debug("\n\n\n\n\n\t\t\t\t\t******************* ON MESSAGE ****************************")
                    logger.debug("Mqtt - Received on_message {topic} {payload}".format(
                        topic=topic, payload=format_str(payload, is_json=True)))

                    parts = str(msg.topic).split('/')
                    device_id = db.get_device_id(parts[5])
                    if not device_id:
                        logger.warning("Mqtt - channel_id {} not found in database.".format(parts[5]))
                        return

                    case = {
                        "device_id": device_id,
                        "channel_id": parts[5],
                        "component": parts[7],
                        "property": parts[9]
                    }

                    if "data" in payload:
                        data = payload["data"]
                    else:
                        data = None

                    sender = {
                        "client_id": payload["sender"],
                        "owner_id": payload["on_behalf_of"]
                    }

                    credentials = db.get_credentials(
                        payload["sender"], payload["on_behalf_of"], case["channel_id"])

                    if not credentials:
                        logger.error("Mqtt - credentials not found in database.")
                        return

                    validated_credentials = implementer.access_check(
                        mode='r', case=case, credentials=credentials, sender=sender)
                    if validated_credentials is not None:

                        logger.debug("inside the access check")
                        if payload["io"] == "r":
                            result = implementer.upstream(
                                mode='r', case=case, credentials=validated_credentials, sender=sender, data=data)
                            if result != None:
                                self.publisher(io="ir", data=result, case=case)
                            else:
                                return
                        elif payload["io"] == "w":
                            result = implementer.upstream(
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
        except Exception as ex:
            logger.error("Mqtt - Failed to handle payload.")
            logger.trace(ex)

    def on_publish(self, client, userdata, mid):
        logger.debug("\n\n\n\n\n\t\t\t\t\t******************* ON PUBLISH ****************************")
        logger.verbose("Mqtt - Publish acknowledged by broker, mid({}) userdata={}.".format(mid, userdata))

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.error("Mqtt - Unexpected disconnection.")
        else:
            logger.error("Mqtt - Expected disconnection.")

    def on_log(self, userdata, level, buf):
        logger.debug("Mqtt - Paho log: {}".format(buf))

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
            except Exception as ex:
                logger.alert("Mqtt - Failed to authenticate SSL certificate")
                logger.trace(ex)
                exit()

            self.mqtt_client.connect(host, port)
            logger.debug( "Mqtt - Did start connect w/ host:{} and port:{}".format(host, port))
            try:
                logger.debug("Mqtt - Will start the loop")
                self.mqtt_client.loop_start()
            except Exception as ex:
                logger.alert("Mqtt - Failed to listen through loop")
                logger.trace(ex)
                exit()

        except Exception as ex:
            logger.emergency(ex)
            logger.trace(ex)
            exit()

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
                    logger.warning(
                        "Mqtt - No channel id found for this device")
                    return

                topic = "/{api_version}/channels/{channel_id}/components/{component}/properties/{property}/value".format(
                    api_version=settings.api_version,
                    channel_id=channel_id,
                    component=case["component"],
                    property=case["property"]
                )
            else:
                logger.warning("Mqtt - Invalid arguements provided to publisher.")
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
        except Exception as ex:
            logger.error("Mqtt - Failed to publish , ex {}".format(ex))
            logger.trace(ex)

    def mqtt_decongif(self):
        try:
            self.mqtt_client.unsubscribe("/{api_version}/managers/{client_id}/channels/#".format(
                api_version=settings.api_version, client_id=settings.client_id))
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            self.mqtt_client.disable_logger()
        except Exception as ex:
            logger.error("Mqtt - Failed to de-configure connection")
            logger.trace(ex)
            exit()


mqtt = MqttConnector()
