import json
import requests
import traceback
import os
from flask import Response
from tenacity import retry, wait_fixed
import concurrent
import asyncio

from base import settings, logger
from base.common.webhook_base import WebhookHubBase
from base.utils import format_str
from base.constants import DEFAULT_RETRY_WAIT

from .polling import PollingManager
from .token_refresher import TokenRefresherManager


class WebhookHubDevice(WebhookHubBase):

    def __init__(self, queue=None, implementer=None):
        super(WebhookHubDevice, self).__init__(queue, implementer)
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
                    if "content" not in element or ("content" in element and not element["content"]):
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
                    payload = request.get_json()
                    logger.verbose(format_str(payload, is_json=True))
                    paired_devices = payload["channels"]
                    if not paired_devices:
                        logger.error("No paired devices found in request: {}".format(payload))
                else:
                    return Response(status=422)

                owner_id = request.headers["X-Owner-Id"]
                client_id = request.headers["X-Client-Id"]
                channel_template = request.headers["X-Channeltemplate-Id"]

                credentials = self.db.get_credentials(client_id, owner_id)
                channels = []

                if paired_devices:
                    loop = asyncio.new_event_loop()
                    responses = loop.run_until_complete(self.send_channel_requests(paired_devices,
                                                                                   credentials,
                                                                                   client_id,
                                                                                   owner_id,
                                                                                   channel_template))
                    loop.close()
                    channels = [{"id": channel_id} for channel_id in responses]

                logger.info(channels)

                sender = {
                    "channel_template_id": channel_template,
                    "client_id": client_id,
                    "owner_id": owner_id
                }

                self.implementer.did_pair_devices(sender=sender,
                                                  credentials=credentials,
                                                  paired_devices=paired_devices,
                                                  channels=channels)

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

    async def send_channel_requests(self, devices, credentials, client_id, owner_id, channel_template):
        loop = asyncio.get_event_loop()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                loop.run_in_executor(
                    executor,
                    self.channels_grant,
                    device, credentials, client_id, owner_id, channel_template
                )
                for device in devices
            ]

            return await asyncio.gather(*futures)

    def channels_grant(self, device, credentials, client_id, owner_id, channel_template):

        try:
            channel_template = self.implementer.update_channel_template(device['id']) or channel_template
            channel_id = self.get_or_create_channel(device, channel_template)

            # Granting permission to intervenient with id X-Client-Id
            url = "{}/channels/{}/grant-access".format(settings.api_server_full, channel_id)

            try:
                data = {
                    "client_id": client_id,
                    "role": "application"
                }

                logger.debug("Initiated POST - {}".format(url))
                logger.verbose(format_str(data, is_json=True))

                resp_app = self.session.post(url, json=data)
                logger.debug("Received response code[{}]".format(resp_app.status_code))

                if resp_app.status_code not in (201, 200):
                    logger.debug(format_str(resp_app.json(), is_json=True))
                    return False
            except Exception:
                logger.error("Failed to grant access to client {} {}".format(
                    client_id,
                    traceback.format_exc(limit=5))
                )
                return False

            # Granting permission to intervenient with id X-Owner-Id
            try:
                data = {
                    "client_id": owner_id,
                    "requesting_client_id": client_id,
                    "role": "user"
                }

                logger.debug("Initiated POST - {}".format(url))
                logger.verbose(format_str(data, is_json=True))

                resp_user = self.session.post(url, json=data)
                logger.verbose("Received response code[{}]".format(resp_user.status_code))

                if resp_user.status_code not in (201, 200):
                    logger.debug(format_str(resp_user.json(), is_json=True))
                    return False
            except Exception:
                logger.error("Failed to grant access to owner {} {}".format(
                    channel_template,
                    traceback.format_exc(limit=5)))
                return False

            client_app_id = credentials['client_id']
            old_credentials = self.db.get_credentials(client_id, owner_id, channel_id)
            if old_credentials and 'refresh_token' in credentials:
                old_credentials = self.implementer.auth_response(old_credentials)
                self.db.update_all_owners(old_credentials, credentials, channel_id, client_app_id, True)
                self.db.update_all_channels(old_credentials, credentials, owner_id, client_app_id, True)

            self.db.set_credentials(credentials, client_id, owner_id, channel_id)
            return channel_id

        except Exception as e:
            logger.error('Error while requesting grant {}'.format(e))

        return None

    def get_or_create_channel(self, device, channel_template):
        try:
            channel_id = self.db.get_channel_id(device["id"])

            # Validate if still exists on Muzzley
            url = "{}/channels/{}".format(settings.api_server_full, channel_id)
            resp = self.session.get(url, data=None)
            logger.verbose("/v3/channels/{} response code {}".format(channel_id, resp.status_code))

            if resp.status_code not in (200, 201):
                channel_id = self.create_channel_id(device, channel_template)

                # Ensure persistence of manufacturer's device id (key) to channel id (field) in redis hash
                self.db.set_channel_id(device["id"], channel_id, True)
                logger.verbose("Channel added to database {}".format(channel_id))

            return channel_id

        except Exception as e:
            logger.error('Error get_or_create_channel {}'.format(e))

        return None

    def create_channel_id(self, device, channel_template):

        # Creating a new channel for the particular device"s id
        data = {
            "name": device.get("content", "Device"),
            "channeltemplate_id": channel_template
        }

        try:
            logger.debug("Initiated POST - {}".format(settings.api_server_full))
            logger.verbose(format_str(data, is_json=True))

            resp = self.session.post("{}/managers/self/channels".format(settings.api_server_full), json=data)

            logger.debug("Received response code[{}]".format(resp.status_code))

            if resp.status_code != 201:
                logger.debug(format_str(resp.json(), is_json=True))
                raise Exception

        except Exception as e:
            logger.error(
                "Failed to create channel for channel template {} {}".format(channel_template,
                                                                             traceback.format_exc(limit=5)))
            return Response(status=400)

        return resp.json()["id"]

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
