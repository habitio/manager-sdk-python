import json
import logging
import traceback

import requests
from flask import request, Response

from base.mqtt_connector import mqtt
from base.redis_db import db
from base.settings import settings
from base.solid import implementer
from base.utils import format_str
from base.polling import poll
from base.token_refresher import refresher

logger = logging.getLogger(__name__)


class WebhookHub:

    def __init__(self):
        self.confirmation_hash = ""
        self.implementer = implementer
        self.poll = poll
        self.refresher = refresher

    def webhook_registration(self):
        logger.debug("\n\n\n\t\t\t\t********************** REGISTERING WEBHOOK **************************")
        full_host = "{}://{}/{}".format(settings.schema_pub, settings.host_pub, settings.api_version)
        data = {
            "authorize": "{}/authorize".format(full_host),
            "receive_token": "{}/receive_token".format(full_host),
            "devices_list": "{}/devices_list".format(full_host),
            "select_device": "{}/select_device".format(full_host)
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        }
        url = settings.webhook_url
        try:
            logger.debug("Initiated PATCH - {}".format(url))
            logger.verbose(format_str(data, is_json=True))

            resp = requests.patch(url, data=json.dumps(data), headers=headers)

            logger.verbose("Received response code[{}]".format(resp.status_code))
            logger.verbose(format_str(resp.json(), is_json=True))

            if "confirmation_hash" in resp.json():
                self.confirmation_hash = resp.json()["confirmation_hash"]
                print("Confirmation Hash : {}".format(self.confirmation_hash))
                logger.notice("Confirmation Hash received!")
            else:
                raise Exception

            self.implementer.start()
            self.poll.start()
            self.refresher.start()

        except Exception as e:
            logger.alert("Failed to get confirmation hash! {}".format(traceback.format_exc(limit=5)))
            exit()

    # .../authorize Webhook
    def authorize(self, request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t********************** AUTHORIZE **************************")
        logger.debug("Received {} - {}".format(request.method, request.path))
        logger.verbose("\n" + str(request.headers))
        try:
            received_hash = request.headers.get("Authorization").replace("Bearer ", "")
            if received_hash == self.confirmation_hash:
                sender = {
                    "channel_template_id": request.headers["X-Channeltemplate-Id"],
                    "client_id": request.headers["X-Client-Id"],
                    "owner_id": request.headers["X-Owner-Id"]
                }
                data = {
                    "location": self.implementer.auth_requests(sender=sender)
                }

                return Response(
                    response=json.dumps(data),
                    status=200,
                    mimetype="application/json"
                )
            else:
                logger.debug("Provided invalid confirmation hash!")
                return Response(status=403)
        except Exception as e:
            logger.error("Couldn't complete processing request, {}".format(traceback.format_exc(limit=5)))

    # .../receive_token Webhook
    def receive_token(self, request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t********************** RECEIVE_TOKEN **************************")
        logger.debug("Received {} - {}".format(request.method, request.path))
        logger.verbose("headers: {}".format(request.headers))
        try:
            received_hash = request.headers.get("Authorization").replace("Bearer ", "")
            if received_hash == self.confirmation_hash:
                if request.is_json:
                    received_data = request.get_json()
                else:
                    return Response(status=422)

                data = self.implementer.auth_response(received_data)
                if data != None:
                    db.set_credentials(data, request.headers["X-Client-Id"], request.headers["X-Owner-Id"])
                    return Response(status=200)
                else:
                    logger.warning("No credentials to be stored!")
                    return Response(status=401)
            else:
                logger.debug("Provided invalid confirmation hash!")
                return Response(status=403)
        except Exception as e:
            logger.error("Couldn't complete processing request, {}".format(traceback.format_exc(limit=5)))

    # .../devices_list Webhook
    def devices_list(self, request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t********************** LIST_DEVICES **************************")
        logger.debug("Received {} - {}".format(request.method, request.path))
        logger.verbose("headers: {}".format(request.headers))
        try:
            received_hash = request.headers.get("Authorization").replace("Bearer ", "")
            if received_hash == self.confirmation_hash:
                credentials = db.get_credentials(request.headers["X-Client-Id"], request.headers["X-Owner-Id"])

                if not credentials:
                    logger.error("No credentials found in database")
                    return Response(
                        status=404
                    )

                sender = {
                    "channel_template_id": request.headers["X-Channeltemplate-Id"],
                    "client_id": request.headers["X-Client-Id"],
                    "owner_id": request.headers["X-Owner-Id"]
                }
                data = self.implementer.get_devices(sender=sender, credentials=credentials)

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
        except Exception as e:
            logger.error("Couldn't complete processing request, {}".format(traceback.format_exc(limit=5)))

    # .../select_device Webhook
    def select_device(self, request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t*******************SELECT_DEVICE****************************")
        logger.debug("Received " + request.method + " - " + request.path)
        logger.verbose("headers: {}".format(request.headers))
        try:
            received_hash = request.headers.get("Authorization").replace("Bearer ", "")
            if received_hash == self.confirmation_hash:
                if request.is_json:
                    logger.verbose(format_str(request.get_json(), is_json=True))
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
                for device in message:
                    channel_id = db.get_channel_id(device["id"])
                    if channel_id:
                        logger.info("Channel already in database")
                        channel = {
                            "id": channel_id
                        }

                        # Validate if still exists on Muzzley
                        url = "{}/channels/{}".format(settings.api_server_full, channel["id"])

                        resp = requests.get(url, headers=headers, data=None)
                        logger.verbose("Received response code[{}]".format(resp.status_code))
                        if int(resp.status_code) not in (200, 201):
                            channel = self.create_channel_id(device)
                        else:
                            logger.info("Channel still valid in Muzzley")
                    else:
                        channel = self.create_channel_id(device)

                    # Granting permission to intervenient with id X-Client-Id

                    url = "{}/channels/{}/grant-access".format(settings.api_server_full, channel["id"])
                    try:
                        data = {
                            "client_id": request.headers["X-Client-Id"],
                            "role": "application"
                        }
                        logger.debug("Initiated POST - {}".format(url))
                        logger.verbose(format_str(data, is_json=True))

                        resp1 = requests.post(url, headers=headers, data=json.dumps(data))

                        logger.debug("Received response code[{}]".format(resp1.status_code))
                        if int(resp1.status_code) not in (201, 200):
                            logger.debug(format_str(resp1.json(), is_json=True))
                            raise Exception
                    except:
                        logger.error("Failed to grant access to client {} {}".format(
                            request.headers["X-Client-Id"],
                            traceback.format_exc(limit=5))
                        )
                        return Response(status=400)

                    # Granting permission to intervenient with id X-Owner-Id
                    try:
                        data = {
                            "client_id": request.headers["X-Owner-Id"],
                            "requesting_client_id": request.headers["X-Client-Id"],
                            "role": "user"
                        }

                        logger.debug("Initiated POST - {}".format(url))
                        logger.verbose(format_str(data, is_json=True))

                        resp2 = requests.post(url, headers=headers, data=json.dumps(data))

                        logger.verbose("Received response code[{}]".format(resp2.status_code))
                        if int(resp2.status_code) not in (201, 200):
                            logger.debug(format_str(resp2.json(), is_json=True))
                            raise Exception
                    except:
                        logger.error("Failed to grant access to owner {} {}".format(request.headers["X-Owner-Id"],
                                                                                    traceback.format_exc(limit=5)))
                        return Response(status=400)

                    channels.append(channel)

                credentials = db.get_credentials(request.headers["X-Client-Id"], request.headers["X-Owner-Id"])
                db.set_credentials(credentials, request.headers["X-Client-Id"], request.headers["X-Owner-Id"],
                                   channel["id"])

                sender = {
                    "channel_template_id": request.headers["X-Channeltemplate-Id"],
                    "client_id": request.headers["X-Client-Id"],
                    "owner_id": request.headers["X-Owner-Id"]
                }
                paired_devices = message
                self.implementer.did_pair_devices(sender=sender, credentials=credentials, paired_devices=paired_devices)

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
        except Exception as e:
            logger.error("Couldn't complete processing request, {}".format(traceback.format_exc(limit=5)))

    def create_channel_id(self, device):
        # Creating a new channel for the particular device"s id
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        }
        data = {
            "name": "Device" if not "content" in device else device["content"],
            "channeltemplate_id": request.headers["X-Channeltemplate-Id"]
        }
        url = settings.api_server_full

        try:
            logger.debug("Initiated POST" + " - " + url)
            logger.verbose("\n" + json.dumps(data, indent=4, sort_keys=True) + "\n")

            resp = requests.post("{}/managers/self/channels".format(url), headers=headers, data=json.dumps(data))

            logger.debug("Received response code[{}]".format(resp.status_code))
            if int(resp.status_code) != 201:
                logger.debug(format_str(resp.json(), is_json=True))
                raise Exception
        except Exception as ex:
            logger.error(
                "Failed to create channel for channel template {} {}".format(request.headers["X-Channeltemplate-Id"],
                                                                             traceback.format_exc(limit=5)))
            return Response(
                status=400
            )

        # Ensure persistance of manufacturer"s device id (key) to channel id (field) in redis hash
        logger.verbose("Channel added to database")
        db.set_channel_id(device["id"], resp.json()["id"], True)

        channel = resp.json()
        return channel

    # .../manufacturer Webhook
    def agent(self, request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t*******************MANUFACTURER****************************")
        logger.debug("Received {} - {}".format(request.method, request.path))
        logger.verbose("\n" + str(request.headers))

        if request.is_json:
            logger.verbose(format_str(request.get_json(), is_json=True))
        else:
            logger.verbose("\n" + request.get_data(as_text=True))

        case, data = implementer.downstream(request)
        if case != None:
            mqtt.publisher(io="iw", data=data, case=case)


# Creating an instance of WebhookHub
webhook = WebhookHub()
