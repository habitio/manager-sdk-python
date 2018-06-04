from base.settings import settings
from base.redis_db import db
from base.mqtt_connector import mqtt 
from base.solid import implementer
from flask import request,Response
import logging, requests, json

logger = logging.getLogger(__name__)

class WebhookHub:

    def __init__(self):
        self.confirmation_hash = ""
        self.implementer = implementer

    def webhook_registration(self):
        logger.debug("\n\n\n\t\t\t\t********************** REGISTERING WEBHOOK **************************")
        full_host = settings.schema_pub+"://"+settings.host_pub
        data = {
            "authorize" : full_host+"/"+settings.api_version+"/authorize",
            "receive_token": full_host+"/"+settings.api_version+"/receive_token",
            "devices_list": full_host+"/"+settings.api_version+"/devices_list",
            "select_device": full_host+"/"+settings.api_version+"/select_device"
        }
        
        headers = {
            "Content-Type" : "application/json",
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        }  
        url = settings.webhook_url
        try:
            logger.debug("Initiated PATCH"+" - "+url)
            logger.verbose("\n"+json.dumps(data,indent=4,sort_keys=True)+"\n")

            resp = requests.patch(url, data=json.dumps(data), headers=headers)
            
            logger.verbose("Received response code["+str(resp.status_code)+"]") 
            logger.verbose("\n"+json.dumps(resp.json(),indent=4,sort_keys=True)+"\n")

            if "confirmation_hash" in resp.json() :
                self.confirmation_hash = resp.json()["confirmation_hash"]
                print("Confirmation Hash : "+self.confirmation_hash)
                logger.notice("Confirmation Hash received!")
            else :
                raise Exception
        except Exception as ex:
            logger.alert("Failed to get confirmation hash! \n"+json.dumps(resp.json(),indent=4,sort_keys=True)+"\n")
            exit()


    # .../authorize Webhook
    def authorize(self,request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t********************** AUTHORIZE **************************")
        logger.debug("Received "+request.method+" - "+request.path)
        logger.verbose("\n"+str(request.headers))
        try:
            received_hash = request.headers.get("Authorization").replace("Bearer ","")
            if received_hash == self.confirmation_hash :

                data = {
                    "location" : self.implementer.auth_requests()
                }
                
                return Response(
                    response=json.dumps(data),
                    status=200, 
                    mimetype="application/json"
                )
            else:
                logger.debug("Provided invalid confirmation hash!")
                return Response(
                    status=403
                )
        except Exception as ex:
            logger.error("Couldn't complete processing request \n")
            logger.trace(ex)
        

    # .../receive_token Webhook
    def receive_token(self,request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t********************** RECEIVE_TOKEN **************************")
        logger.debug("Received "+request.method+" - "+request.path)
        logger.verbose("\n"+str(request.headers))
        try:
            received_hash = request.headers.get("Authorization").replace("Bearer ","")
            if received_hash == self.confirmation_hash :
                if request.is_json:
                    logger.verbose("\n"+json.dumps(request.get_json(),indent=4, sort_keys=True)) 
                    received_data=request.get_json()
                else:
                    return Response(
                        status=422
                    )
                
                data = self.implementer.auth_response(received_data)
                if data != None:
                    db.set_credentials(self, data, request.headers["X-Client-Id"], request.headers["X-Owner-Id"])
                    return Response(
                        status=200
                    )
                else:
                    logger.warning("No credentials to be stored!")
                    return Response(
                        status=401
                    )
            else:
                logger.debug("Provided invalid confirmation hash!")
                return Response(
                    status=403
                )
        except Exception as ex:
            logger.error("Couldn't complete processing request \n")
            logger.trace(ex)


    # .../devices_list Webhook
    def devices_list(self,request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t********************** LIST_DEVICES **************************")
        logger.debug("Received "+request.method+" - "+request.path)
        logger.verbose("\n"+str(request.headers))
        try:
            received_hash = request.headers.get("Authorization").replace("Bearer ","")
            if received_hash == self.confirmation_hash :
                key = request.headers["X-Owner-Id"]
                # if db.has_key(key):
                #     credentials  = db.get_key(key)

                credentials = db.get_credentials(headers["X-Client-Id"], headers["X-Owner-Id"])    

                if not credentials :
                        logger.error("No credentials found in database")
                return Response(
                    status=404
                )

                sender = {
                    "channel_template_id":request.headers["X-Channeltemplate-Id"],
                    "client_id":request.headers["X-Client-Id"],
                    "owner_id":request.headers["X-Owner-Id"]
                }
                data = self.implementer.get_devices(sender=sender,credentials=credentials)

                return Response(
                    response=json.dumps(data),
                    status=200,
                    mimetype="application/json"
                )
                # else:
                   
            else:
                logger.debug("Provided invalid confirmation hash!")
                return Response(
                    status=403
                )
        except Exception as ex:
            logger.error("Couldn't complete processing request \n")
            logger.trace(ex)


    # .../select_device Webhook
    def select_device(self,request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t*******************SELECT_DEVICE****************************")
        logger.debug("Received "+request.method+" - "+request.path)
        logger.verbose("\n"+str(request.headers))
        try:
            received_hash = request.headers.get("Authorization").replace("Bearer ","")
            if received_hash == self.confirmation_hash :
                if request.is_json:
                    logger.verbose("\n"+json.dumps(request.get_json(),indent=4, sort_keys=True))
                    message = request.get_json()["channels"]
                else:
                    return Response(
                        status=422
                    )

                headers = {
                        "Content-Type": "application/json",
                        "Authorization": "Bearer {0}".format(settings.block["access_token"])
                    }

                channels = []
                for device in message :
                    if db.has_key(device["id"]):
                        logger.info("Channel already in database")
                        channel = {
                            "id" : str(db.get_key(device["id"]))
                        }

                        #Validate if still exists on Muzzley
                        url = settings.api_server_full+"/channels/" + channel["id"]

                        resp = requests.get(url, headers=headers, data=None)
                        logger.verbose("Received response code["+str(resp.status_code)+"]")
                        if int(resp.status_code) not in (200,201):
                            channel = self.create_channel_id(device)
                        else:
                            logger.info("Channel still valid in Muzzley")
                    else:
                        channel = self.create_channel_id(device)

                    #Granting permission to intervenient with id X-Client-Id
                    
                    url = settings.api_server_full+"/channels/" + channel["id"] + "/grant-access"
                    try:
                        data = { 
                            "client_id" : request.headers["X-Client-Id"], 
                            "role" : "application" 
                        }
                        logger.debug("Initiated POST"+" - "+url)
                        logger.verbose("\n"+json.dumps(data,indent=4,sort_keys=True)+"\n")

                        resp1 = requests.post(url, headers=headers, data=json.dumps(data))

                        logger.debug("Received response code["+str(resp1.status_code)+"]")
                        if int(resp1.status_code) not in (201,200):
                            logger.debug("\n"+json.dumps(resp1.json(),indent=4,sort_keys=True)+"\n")
                            raise Exception 
                    except:
                        logger.error("Failed to grant access to client "+str(request.headers["X-Client-Id"]))
                        return Response(
                            status=400
                        )

                    #Granting permission to intervenient with id X-Owner-Id
                    try:
                        data = { 
                            "client_id" : request.headers["X-Owner-Id"], 
                            "requesting_client_id" : request.headers["X-Client-Id"], 
                            "role" : "user" 
                        }
                    
                        logger.debug("Initiated POST"+" - "+url)
                        logger.verbose("\n"+json.dumps(data,indent=4,sort_keys=True)+"\n")

                        resp2 = requests.post(url, headers=headers, data=json.dumps(data))
                        
                        logger.verbose("Received response code["+str(resp2.status_code)+"]")
                        if int(resp2.status_code) not in (201,200):
                                logger.debug("\n"+json.dumps(resp2.json(),indent=4,sort_keys=True)+"\n")
                                raise Exception
                    except:
                        logger.error("Failed to grant access to owner "+str(request.headers["X-Owner-Id"]))
                        return Response(
                            status=400
                        )

                    channels.append(channel)

                # key = request.headers["X-Owner-Id"]
                # if db.has_key(key):
                #     db.get_key(key)
                
                credentials = db.get_credentials(request.headers["X-Client-Id"], request.headers["X-Owner-Id"])
                db.set_credentials(credentials, request.headers["X-Client-Id"], request.headers["X-Owner-Id"], channel["id"])

                sender = {
                    "channel_template_id": request.headers["X-Channeltemplate-Id"],
                    "client_id" :request.headers["X-Client-Id"],
                    "owner_id" :request.headers["X-Owner-Id"]
                }
                paired_devices = message
                self.implementer.did_pair_devices(sender=sender,credentials=credentials,paired_devices=paired_devices)

                return Response(
                    response=json.dumps(channels),
                    status=200,
                    mimetype="application/json"
                )
            else:
                logger.debug("Provided invalid confirmation hash!")
                return Response(
                    status=403
                )
        except Exception as ex:
            logger.error("Couldn't complete processing request \n")
            logger.trace(ex)


    def create_channel_id(self, device):
        # Creating a new channel for the particular device"s id
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        }
        data = { 
            "name" : "Device" if not "content" in device else device["content"],
            "channeltemplate_id": request.headers["X-Channeltemplate-Id"]
        }
        url = settings.api_server_full

        try:
            logger.debug("Initiated POST"+" - "+url)
            logger.verbose("\n"+json.dumps(data,indent=4,sort_keys=True)+"\n")

            resp = requests.post(url+"/managers/self/channels",headers=headers , data=json.dumps(data))

            logger.debug("Received response code["+str(resp.status_code)+"]") 
            if int(resp.status_code) != 201:
                logger.debug("\n"+json.dumps(resp.json(),indent=4,sort_keys=True)+"\n")
                raise Exception
        except Exception as ex:
            logger.error("Failed to create channel for channel template "+str(request.headers["X-Channeltemplate-Id"]))
            logger.trace(ex)
            return Response(
                status=400
            )
        
        #Ensure persistance of manufacturer"s device id (key) to channel id (field) in redis hash
        logger.verbose("Channel added to database")
        db.set_key(device["id"],resp.json()["id"],by_value=True)

        channel = resp.json()
        return channel
    

    # .../manufacturer Webhook
    def agent(self,request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t*******************MANUFACTURER****************************")
        logger.debug("Received "+request.method+" - "+request.path)
        logger.verbose("\n"+str(request.headers))

        if request.is_json:
            logger.verbose("\n"+json.dumps(request.get_json(),indent=4, sort_keys=True))
        else:
            logger.verbose("\n"+request.get_data(as_text=True))
        
        case,data = implementer.downstream(request)
        if case != None:
            mqtt.publisher(io="iw",data=data,case=case)
        
#Creating an instance of WebhookHub
webhook = WebhookHub()
