import json
import logging
import requests
import traceback
import os
from flask import Response, request
from tenacity import retry, wait_fixed

from base import settings
from base.common.webhook_base import WebhookHubBase
from base.redis_db import get_redis
from base.utils import format_str
from base.constants import DEFAULT_RETRY_WAIT

from .polling import PollingManager
from .token_refresher import TokenRefresherManager

logger = logging.getLogger(__name__)

class WebhookHubDevice(WebhookHubBase):

    def __init__(self, mqtt=None, implementer=None):
        super(WebhookHubDevice, self).__init__(mqtt, implementer)
        self.confirmation_hash = ""

        try:
            self.refresher = TokenRefresherManager(implementer=self.implementer)
        except Exception as e:
            logger.error("Failed start TokenRefresher manager, {} {}".format(e, traceback.format_exc(limit=5)))
            self.refresher = None

        try:
            self.poll = PollingManager(implementer=self.implementer)
        except Exception as e:
            logger.error("Failed start Polling manager, {} {}".format(e, traceback.format_exc(limit=5)))
            self.poll = None


    def authorize(self, request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t********************** AUTHORIZE **************************")
        logger.debug("Received {} - {}".format(request.method, request.path))
        logger.verbose("headers: {}".format(request.headers))

        try:
            received_hash = request.headers.get("Authorization", "").replace("Bearer ", "")
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
                logger.debug("Provided invalid confirmation hash! {}".format(self.confirmation_hash))
                return Response(status=403)
        except Exception as e:
            logger.error("Couldn't complete processing request, {}".format(traceback.format_exc(limit=5)))

        return Response(status=403)

    def devices_list(self, request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t********************** LIST_DEVICES **************************")
        logger.debug("Received {} - {}".format(request.method, request.path))
        logger.verbose("headers: {}".format(request.headers))

        try:
            received_hash = request.headers.get("Authorization", "").replace("Bearer ", "")
            if received_hash == self.confirmation_hash:
                credentials = self.db.get_credentials(request.headers["X-Client-Id"], request.headers["X-Owner-Id"])

                if not credentials:
                    logger.error("No credentials found in database")
                    return Response(status=404)

                sender = {
                    "channel_template_id": request.headers["X-Channeltemplate-Id"],
                    "client_id": request.headers["X-Client-Id"],
                    "owner_id": request.headers["X-Owner-Id"]
                }
                data = self.implementer.get_devices(sender=sender, credentials=credentials)

                for element in data:
                    if not "content" in element or ("content" in element and not element["content"]):
                        element["content"] = ""

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

        return Response(status=403)

    def select_device(self, request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t*******************SELECT_DEVICE****************************")
        logger.debug("Received {} - {}".format(request.method, request.path))
        logger.verbose("headers: {}".format(request.headers))

        try:
            received_hash = request.headers.get("Authorization", "").replace("Bearer ", "")
            if received_hash == self.confirmation_hash:

                if request.is_json:
                    logger.verbose(format_str(request.get_json(), is_json=True))
                    paired_devices = request.get_json()["channels"]
                else:
                    return Response(status=422)



                credentials = self.db.get_credentials(request.headers["X-Client-Id"], request.headers["X-Owner-Id"])
                channels = []

                for device in paired_devices:
                    channel_id = self.db.get_channel_id(device["id"])
                    if channel_id:
                        logger.info("Channel already in database")
                        channel = {
                            "id": channel_id
                        }

                        # Validate if still exists on Muzzley
                        url = "{}/channels/{}".format(settings.api_server_full, channel["id"])
                        resp = self.session.get(url, data=None)
                        logger.verbose("Received response code[{}]".format(resp.status_code))

                        if int(resp.status_code) not in (200, 201):
                            channel = self.create_channel_id(device)
                        else:
                            logger.info("Channel still valid in Muzzley")

                            # Ensure persistence of manufacturer's device id (key) to channel id (field) in redis hash
                            self.db.set_channel_id(device["id"], channel_id, True)
                            logger.verbose("Channel added to database")
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

                        resp1 = self.session.post(url, json=data)
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

                        resp2 = self.session.post(url, json=data)
                        logger.verbose("Received response code[{}]".format(resp2.status_code))

                        if int(resp2.status_code) not in (201, 200):
                            logger.debug(format_str(resp2.json(), is_json=True))
                            raise Exception
                    except:
                        logger.error("Failed to grant access to owner {} {}".format(
                            request.headers["X-Owner-Id"],
                            traceback.format_exc(limit=5)))
                        return Response(status=400)

                    channels.append(channel)
                    self.db.set_credentials(credentials, request.headers["X-Client-Id"], request.headers["X-Owner-Id"],
                                   channel["id"])

                sender = {
                    "channel_template_id": request.headers["X-Channeltemplate-Id"],
                    "client_id": request.headers["X-Client-Id"],
                    "owner_id": request.headers["X-Owner-Id"]
                }

                self.implementer.did_pair_devices(sender=sender, credentials=credentials, paired_devices=paired_devices)

                return Response(
                    response=json.dumps(channels),
                    status=200,
                    mimetype="application/json"
                )
            else:
                logger.debug("Provided invalid confirmation hash!")
                return Response(status=403)
        except Exception as e:
            logger.error("Couldn't complete processing request, {}".format(traceback.format_exc(limit=5)))

        return Response(status=403)

    def create_channel_id(self, device):

        # Creating a new channel for the particular device"s id
        data = {
            "name": "Device" if not "content" in device else device["content"],
            "channeltemplate_id": request.headers["X-Channeltemplate-Id"]
        }
        url = settings.api_server_full

        try:
            logger.debug("Initiated POST - {}".format(url))
            logger.verbose(format_str(data, is_json=True))

            resp = self.session.post("{}/managers/self/channels".format(url), json=data)

            logger.debug("Received response code[{}]".format(resp.status_code))

            if int(resp.status_code) != 201:
                logger.debug(format_str(resp.json(), is_json=True))
                raise Exception

        except Exception as ex:
            logger.error(
                "Failed to create channel for channel template {} {}".format(request.headers["X-Channeltemplate-Id"],
                                                                             traceback.format_exc(limit=5)))
            return Response(status=400)

        # Ensure persistence of manufacturer"s device id (key) to channel id (field) in redis hash
        logger.verbose("Channel added to database")
        self.db.set_channel_id(device["id"], resp.json()["id"], True)

        channel = resp.json()
        return channel

    @retry(wait=wait_fixed(DEFAULT_RETRY_WAIT))
    def patch_endpoints(self):
        try:
            full_host = "{}://{}/{}".format(settings.schema_pub, settings.host_pub, settings.api_version)
            data = {
                "authorize": "{}/authorize".format(full_host),
                "receive_token": "{}/receive-token".format(full_host),
                "devices_list": "{}/devices-list".format(full_host),
                "select_device": "{}/select-device".format(full_host)
            }

            url = settings.webhook_url

            logger.debug("Initiated PATCH - {} {}".format(url, self.session.headers))
            logger.verbose(format_str(data, is_json=True))

            resp = requests.patch(url, data=json.dumps(data), headers=self.session.headers)

            logger.verbose("Received response code[{}]".format(resp.status_code))
            logger.verbose(format_str(resp.json(), is_json=True))

            if "confirmation_hash" in resp.json():
                self.confirmation_hash = resp.json()["confirmation_hash"]
                logger.notice("Confirmation Hash : {}".format(self.confirmation_hash))
            else:
                raise Exception

        except Exception as e:
            logger.alert("Failed at patch endpoints! {}".format(traceback.format_exc(limit=5)))
            raise

    def webhook_registration(self):

        try:
            self.patch_endpoints()

            if self.poll:
                self.poll.start() if self.poll.thread is None else \
                    logger.notice("Polling thread alive? : {}".format(self.poll.thread.is_alive()))

            if self.refresher:
                self.refresher.start() if self.refresher.thread is None else \
                    logger.notice("Refresher thread alive? : {}".format(self.refresher.thread.is_alive()))

            if self.watchdog_monitor:
                self.watchdog_monitor.start() if self.watchdog_monitor.thread is None else \
                    logger.notice("Watchdog thread alive? : {}".format(self.watchdog_monitor.thread.is_alive()))

            self.implementer.start()

        except Exception as e:
            logger.alert("Unexpected exception {}".format(traceback.format_exc(limit=5)))
            os._exit(1)
