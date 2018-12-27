
import logging
import traceback
from flask import Response, jsonify
import requests
import json

from base.common.webhook_base import WebhookHubBase
from base.utils import format_str
from base.exceptions import InvalidRequestException
from base.settings import settings


logger = logging.getLogger(__name__)

class WebhookHubHardware(WebhookHubBase):

    def __init__(self):
        super(WebhookHubHardware, self).__init__()

    def inbox(self, request):

        logger.debug("\n\n\n\n\n\t\t\t\t\t******************* HARDWARE_INBOX ****************************")
        logger.debug("Received {} - {}".format(request.method, request.path))
        logger.verbose("\n{}".format(request.headers))

        try:

            if request.is_json:
                logger.verbose('json request {}'.format(format_str(request.get_json(), is_json=True)))
                data = request.get_json()
            else:
                logger.verbose("\n{}".format(request.get_data(as_text=True)))
                data = request.get_data()

            if all(key in data for key in ('namespace', 'name', 'serial', 'channel-template', 'confirmation-hash')):
                is_valid = self.implementer.validate_confirmation_hash(data)
                if is_valid:
                    device = self.create_device(data)
                    if device and type(device) is dict and 'secret' in device and 'device_id' in device:
                        return jsonify(device)

        except Exception:
            logger.error("Unexpected error inbox hardware: {}".format(traceback.format_exc(limit=5)))

        return Response(status=400)

    def create_device(self, data):
        try:
            url = "{}/devices".format(settings.api_server_full)
            device_params = {
                'namespace': data['namespace'],
                'cdata': data['cdata'],
                'name': data['name'],
                'serial': data['serial']
            }

            resp = requests.post(url, data=json.dumps(device_params), headers=self.headers)
            if resp.status_code != requests.codes.created:
                raise InvalidRequestException(resp.json())

            device = self.get_device(resp['href'])
            return device

        except InvalidRequestException as e:
            logger.error('Error while creating new device {}'.format(e))
        except Exception:
            logger.error('Error on hardware create_device'.format(traceback.format_exc(limit=5)))

        return None

    def get_device(self, device_uri):
        try:
            url = "{}/{}".format(settings.api_server, device_uri)
            resp = requests.get(url, headers=self.headers)
            if resp.status_code != requests.codes.created:
                raise InvalidRequestException(resp.json())

            secret = resp['secret']
            device_id = resp['id']

            logger.info('SECRET: {}, DEVICE_ID:{}'.format(secret, device_id))

            return {
                'secret': secret,
                'device_id': device_id
            }

        except InvalidRequestException as e:
            logger.error('Error while creating new device {}'.format(e))
        except Exception:
            logger.error('Error on hardware create_device'.format(traceback.format_exc(limit=5)))

        return None


    def webhook_registration(self):

        try:
            logger.verbose('[Webhook] Skipping webhook registration')
        except Exception as e:
            logger.alert("Unexpected exception {}".format(traceback.format_exc(limit=5)))
            exit()
