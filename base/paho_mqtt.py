from base import auth
from base.settings import settings
from base.redis_db import db
import logging, time
import paho.mqtt.client as paho
import json

logger = logging.getLogger(__name__)


def on_connect(client, userdata, flags, rc):
    try:
        if rc == 0 :
            logger.notice("Mqtt - Connected , result code "+str(rc))
            mqtt_client.subscribe("/"+settings.api_version+"/managers/"+settings.client_id+"/channels/#",qos=0)
        elif rc>0 and rc<6 :
            rc_list = {
                0: "Connection successful",
                1: "Connection refused - incorrect protocol version" ,
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorised",
            }
            raise Exception(rc_list[rc])
    except Exception as ex:
        logger.error("Mqtt - "+str(ex))
        exit()
    
def on_subscribe(client, userdata, mid, granted_qos):
    logger.info("Mqtt - Subscribed , mid("+str(mid)+") qos("+str(granted_qos)+")")

def on_message(client, userdata, msg):
    try:
        from base.solid import implementer

        topic = msg.topic
        payload = json.loads(msg.payload.decode("utf-8"))
        logger.debug("Mqtt - Received "+topic+"  \n"+json.dumps(payload,indent=4,
        sort_keys=True))

        if "io" in payload and payload["io"] in ("r","w"):
            if all (k in payload for k in ("on_behalf_of","sender")):
                parts = str(msg.topic).split('/')
                if db.has_key(parts[5]):
                    device_id = db.get_key(parts[5])
                else:
                    logger.error("Mqtt - channel_id "+parts[5]+" not found in database. ")
                    return

                case = {
                    "device_id" : device_id,
                    "channel_id" : parts[5],
                    "component" :parts[7],
                    "property" :parts[9]
                }

                if "data" in payload:
                    data = payload["data"]
                else:
                    data = None

                sender = {
                    "client_id" : payload["sender"],
                    "owner_id" : payload["on_behalf_of"]
                }

                key = payload["sender"]+"/"+payload["on_behalf_of"]
                if db.has_key(key):
                    credentials = db.get_key(key)
                else:
                    logger.error("Mqtt - credentials not found in database. ")
                    return

                if payload["io"] == "r":
                    result = implementer.upstream(mode='r',case=case,credentials=credentials,sender=sender,data=data)
                    if result != None:
                        publisher(io="ir",data=result,case=case)
                    else:
                        return
                elif payload["io"] == "w":
                    result = implementer.upstream(mode='w',case=case,credentials=credentials,sender=sender,data=data)
                    if result == True:
                        publisher(io="iw",data=data,case=case)
                    elif result == False:
                        return
            else:
                logger.error("Mqtt - No 'sender'/'on_behalf_of' in payload")
                return
        else:
            return
    except Exception as ex:
        logger.error("Mqtt - Failed to handle payload.")
        logger.trace(ex)

def on_publish(client, userdata, mid):   
    logger.debug("Mqtt - Publish acknowledged by broker, mid("+str(mid)+").")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        logger.error("Mqtt - Unexpected disconnection.")
    else:
        logger.error("Mqtt - Expected disconnection.")

mqtt_client = paho.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_subscribe = on_subscribe
mqtt_client.on_message = on_message
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_publish = on_publish

def mqtt_config():
    logger.info("Setting up Mqtt connection")
    try:
        parts = settings.block["mqtt_ep"].split(":")
        schema_mqtt = parts[0]
        host=parts[1].replace("//","")
        port = int(parts[2])

        host = "platform.office.muzzley.com"
        port = 8885
        schema_mqtt = "mqtts"
        
        mqtt_client.username_pw_set(username=settings.client_id,password=settings.block["access_token"])
        try:
            logger.debug("mqtt_client._ssl = {}".format(mqtt_client._ssl))
            if not mqtt_client._ssl and schema_mqtt=="mqtts":
                logger.debug("Will set tls")
                mqtt_client.tls_set(ca_certs='/usr/lib/ssl/certs/ca-certificates.crt')
        except Exception as ex:
            logger.alert("Mqtt - Failed to authenticate SSL certificate")
            logger.trace(ex)
            exit()
        
        mqtt_client.enable_logger()
        mqtt_client.connect(host,port)
        try:
            mqtt_client.loop_start()
        except Exception as ex:
            logger.alert("Mqtt - Failed to listen through loop")
            logger.trace(ex)
            exit()

    except Exception as ex:
        logger.emergency(ex)
        logger.trace(ex)
        exit()
    
def publisher(io,data,case=None):
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

        logger.debug("Mqtt - Case {} and settings.api_version={}".format(case,settings.api_version))

        if all (key in case for key in ("device_id","component","property")):
            channel_id = db.get_key(case["device_id"])
            # logger.debug("Mqtt - Detected channel_id {}".format(channel_id))
            topic = "/"+settings.api_version+"/channels/"+channel_id+"/components/"+case["component"]+"/properties/"+case["property"]+"/value"
            # logger.debug("Mqtt - Created a topic {}".format(topic))
        else:
            logger.warning("Mqtt - Invalid arguements provided to publisher.")
            raise Exception
                
        (rc, mid) = mqtt_client.publish(topic=topic,payload=json.dumps(payload))
        if rc == 0:
            logger.debug("Mqtt - Published to topic {} with payload {}".format(topic, payload))
            logger.debug("Mqtt - Published successfully, result code("+str(rc)+") and mid("+str(mid)+").\n"+json.dumps(data,
            indent=4, sort_keys=True))
        else:
            raise Exception("Mqtt - Failed to publish , result code("+str(rc)+")")
    except Exception as ex:
        logger.error("Mqtt - Failed to publish , ex {}".format(ex))
        logger.trace(ex)

def mqtt_decongif():
    try :
        mqtt_client.unsubscribe("/"+settings.api_version+"/managers/"+settings.client_id+"/channels/#")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        mqtt_client.disable_logger()
    except Exception as ex:
        logger.error("Mqtt - Failed to de-configure connection ")
        logger.trace(ex)
        exit()

