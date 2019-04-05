import json
import traceback

import asyncio
import aiomqtt

from base import settings
from base.redis_db import get_redis
from base.constants import *


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

    def __init__(self, client_id=None, access_token=None,  **kwargs):
        logger.debug("Mqtt async - Init")
        loop = asyncio.get_event_loop()

        self.mqtt_client = aiomqtt.Client(loop)
        self.mqtt_client.loop_start()
        self.mqtt_client.enable_logger()

        self.mqtt_client.on_connect = self.on_connect if 'on_connect' not in kwargs else kwargs['on_connect']
        self.mqtt_client.on_disconnect = self.on_disconnect if 'on_disconnect' not in kwargs else kwargs['on_disconnect']
        self.mqtt_client.on_publish = self.on_publish if 'on_publish' not in kwargs else kwargs['on_publish']

        self.client_id = client_id if client_id else settings.client_id
        self.access_token = access_token if access_token else settings.block["access_token"]
        self.connected = asyncio.Event(loop=loop)
        self.disconnected = asyncio.Event(loop=loop)
        self.db = get_redis()

    def on_connect(self, client, userdata, flags, rc):
        self.connected.set()

    def on_publish(self, client, userdata, mid):
        print("Mqtt - Publish acknowledged by broker, mid({}) userdata={}.".format(mid, userdata))

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            self.disconnected.set()
            print("Mqtt - Unexpected disconnection: {}".format(RC_LIST.get(rc)))
        else:
            print("Mqtt - Expected disconnection.")

    def on_log(self, userdata, level, buf):
        print("Mqtt - Paho log: {}".format(buf))

    async def start_connection(self):
        print("Setting up Mqtt connection")
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

            await self.mqtt_client.connect(host, port=port)
            await self.connected.wait()

            print( "Mqtt - Did start connect w/ host:{} and port:{}".format(host, port))

        except Exception as e:
            print("Unexpected error: {}".format(e, traceback.format_exc(limit=5)))
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
            payload = dict()
            payload["io"] = io

            if data != None:
                payload["data"] = data

            print(
                "Mqtt - Case {} and settings.api_version={}".format(case, "v3"))

            if all(key in case for key in ("device_id", "component", "property")) or all(key in case for key in ("channel_id", "component", "property")):

                channel_id = case["channel_id"] if "channel_id" in case else self.db.get_channel_id(case["device_id"])

                if channel_id is None:
                    print("Mqtt - No channel id found for this device")
                    return

                topic = "/{api_version}/channels/{channel_id}/components/{component}/properties/{property}/value".format(
                    api_version="v3",
                    channel_id=channel_id,
                    component=case["component"],
                    property=case["property"]
                )
            else:

                print("Mqtt - Invalid arguments provided to publisher.")
                raise Exception

            return self.mqtt_client.publish(
                topic=topic, payload=json.dumps(payload))


        except Exception as e:
            print("Mqtt - Failed to publish , ex {}".format(e))
