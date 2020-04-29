import datetime
import sys
import traceback
import json
import os
import requests
from tenacity import retry, wait_fixed
from flask import Response

from base import settings, logger
from base.common.webhook_base import WebhookHubBase
from base.constants import DEFAULT_RETRY_WAIT
from base.exceptions import InvalidRequestException, UnauthorizedException, ValidationException
from base.utils import is_valid_uuid
from base.helpers import validate_quote


class WebhookHubApplication(WebhookHubBase):

    def activate(self, request):

        try:

            return self.implementer.activate(request=request,
                                             client_id=settings.client_id, access_token=settings.block['access_token'])

        except Exception as _e:

            traceback.print_exc(file=sys.stdout)

            return Response(status=501, response=json.dumps({'text': str(_e)}))

    def service_authorize(self, request):

        _service_id = request.path.split('/')[-2]

        for _service in settings.services:

            if _service["id"] == _service_id:

                return Response(
                    status=200,
                    response=json.dumps({
                        "location": {
                            "id": _service["id"],
                            "url": _service.get("url")
                        }
                    }),
                    content_type='application/json'
                )

        return Response(
            status=200,
            response=json.dumps({
                "location": None
            }),
            content_type='application/json'
        )

    @retry(wait=wait_fixed(DEFAULT_RETRY_WAIT))
    def patch_endpoints(self):
        try:
            _data = settings.services

            for _service in _data:

                try:

                    data = {
                        'activation_uri': '{}://{}/{}/services/{}/authorize'.format(settings.schema_pub,
                                                                                    settings.host_pub,
                                                                                    settings.api_version,
                                                                                    _service['id'])
                    }

                    logger.debug("[patch_endpoints] Initiated PATCH - {}".format(_service.get('url')))
                    logger.verbose("\n{}\n".format(json.dumps(data, indent=4, sort_keys=True)))
                    continue

                    resp = requests.patch('{}/services/{}'.format(settings.api_server_full, _service['id']),
                                          data=json.dumps(data), headers=self.session.headers)

                    logger.verbose("[patch_endpoints] Received response code[{}]".format(resp.status_code))
                    logger.verbose("\n{}\n".format(json.dumps(resp.json(), indent=4, sort_keys=True)))

                    if int(resp.status_code) == 200:
                        logger.notice("[patch_endpoints] Service setup successful!")
                    else:
                        raise Exception('Service setup not successful!')

                except Exception as ex:

                    logger.alert("[patch_endpoints] Failed to set service!\n{}".format(ex))
                    os._exit(1)

            # self.patch_custom_endpoints()
            self.set_confirmation_hash()

        except Exception as e:
            logger.alert("[patch_endpoints] Failed at patch endpoints! {}".format(traceback.format_exc(limit=5)))
            raise

    @retry(wait=wait_fixed(DEFAULT_RETRY_WAIT))
    def patch_custom_endpoints(self):
        try:
            custom_endpoints = settings.custom_endpoints
            url = settings.webhook_url
            data = {'quote_actions': {}}

            for endpoint in custom_endpoints:
                data['quote_actions'].update({
                    endpoint['namespace']: f"{settings.schema_pub}://{settings.host_pub}/"
                                           f"{settings.api_version}{endpoint['uri']}"
                })

            if data['quote_actions']:
                logger.debug(f"[patch_custom_endpoints] Initiated PATCH - {url}")
                logger.verbose("\n{}\n".format(json.dumps(data, indent=4, sort_keys=True)))

                resp = requests.patch(url, data=json.dumps(data), headers=self.session.headers)

                logger.verbose("[patch_{}] Received response code[{}]".format(endpoint['namespace'], resp.status_code))
                logger.verbose("\n{}\n".format(json.dumps(resp.json(), indent=4, sort_keys=True)))

                if int(resp.status_code) == 200:
                    logger.notice(f"[patch_custom_endpoints] {endpoint['namespace']} setup successful!")
                else:
                    raise Exception(f"[patch_custom_endpoints] {endpoint['namespace']} setup not successful!")

        except Exception as e:
            logger.alert("Failed at patch endpoint! {}".format(traceback.format_exc(limit=5)))
            raise

    @retry(wait=wait_fixed(DEFAULT_RETRY_WAIT))
    def get_application(self):
        try:
            logger.debug(f"[get_application] Trying to get application data - {settings.webhook_url}")
            resp = requests.get(settings.webhook_url, headers=self.session.headers)
            logger.verbose("[get_application] Received response code[{}]".format(resp.status_code))

            if int(resp.status_code) == 200:
                logger.notice("[get_application] Get application successful!")
                return resp.json()
            else:
                raise Exception('[get_application] Error getting application!')

        except Exception as e:
            logger.alert("Failed while get application! {}".format(traceback.format_exc(limit=5)))
            raise

    def quote_simulate(self, request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t*******************QUOTE_SIMULATE****************************")
        try:
            service_id, quote_id = self._basic_quote_validation(request)
            result = self.implementer.quote_simulate(service_id, quote_id)

            date = '+'.join([datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3], '0000'])
            if result and (result.get('quote_properties') or result.get('coverage_properties')):
                logger.debug("[quote_simulate] Changing quote status to simulated")
                self.implementer.update_quote_state(quote_id, 'simulated', False, simulated_ts=date)

            return Response(status=200, response=json.dumps(result), mimetype="application/json")

        except (ValidationException, InvalidRequestException) as e:
            return Response(status=412, response=json.dumps({'text': str(e), 'code': 0}), mimetype="application/json")
        except UnauthorizedException as e:
            return Response(status=403, response=json.dumps({'text': str(e), 'code': 0}), mimetype="application/json")
        except Exception:
            logger.error("[quote_simulate] Couldn't complete processing request, {}".format(traceback.format_exc(limit=5)))
            return Response(status=500, response=json.dumps({'text': "Error processing request", 'code': 0}),
                            mimetype="application/json")

    def quote_setup(self, request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t*******************QUOTE_SETUP****************************")
        try:
            service_id, quote_id = self._basic_quote_validation(request)
            result = self.implementer.quote_setup(service_id, quote_id)

            return Response(status=200, response=json.dumps(result), mimetype="application/json")

        except (ValidationException, InvalidRequestException) as e:
            return Response(status=412, response=json.dumps({'text': str(e), 'code': 0}), mimetype="application/json")
        except UnauthorizedException as e:
            return Response(status=403, response=json.dumps({'text': str(e), 'code': 0}), mimetype="application/json")
        except Exception:
            logger.error("[quote_setup] Couldn't complete processing request, {}".format(traceback.format_exc(limit=5)))
            return Response(status=500, response=json.dumps({'text': "Error processing request", 'code': 0}),
                            mimetype="application/json")

    def quote_checkout(self, request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t*******************QUOTE_CHECKOUT****************************")
        try:
            service_id, quote_id = self._basic_quote_validation(request)
            result = self.implementer.quote_checkout(service_id, quote_id)

            return Response(status=200, response=json.dumps(result), mimetype="application/json")

        except (ValidationException, InvalidRequestException) as e:
            return Response(status=412, response=json.dumps({'text': str(e), 'code': 0}), mimetype="application/json")
        except UnauthorizedException as e:
            return Response(status=403, response=json.dumps({'text': str(e), 'code': 0}), mimetype="application/json")
        except Exception:
            logger.error("[quote_checkout] Couldn't complete processing request, {}".format(traceback.format_exc(limit=5)))
            return Response(status=500, response=json.dumps({'text': "Error processing request", 'code': 0}),
                            mimetype="application/json")

    def webhook_registration(self):
        try:
            if self.watchdog_monitor:
                self.watchdog_monitor.start() if self.watchdog_monitor.thread is None else \
                    logger.notice("Watchdog thread alive? : {}".format(self.watchdog_monitor.thread.is_alive()))

            self.implementer.start()

        except Exception as e:
            logger.alert("Unexpected exception {}".format(traceback.format_exc(limit=5)))
            os._exit(1)

    def _basic_quote_validation(self, request):
        logger.debug(f"Received {request.method} - {request.path}")
        logger.verbose(f"headers: {request.headers}")
        received_hash = request.headers.get("Authorization", "").replace("Bearer ", "")
        if self._validate_confirmation_hash(received_hash):
            data = request.json
            if not data:
                raise InvalidRequestException("Missing Payload")
            service_id = data.get('service_id')
            quote_id = data.get('quote_id')
            if not (service_id
                    and is_valid_uuid(service_id)
                    and service_id in [_service['id'] for _service in settings.services]):
                raise InvalidRequestException("Invalid Service")
            if not (quote_id
                    and is_valid_uuid(quote_id)
                    and validate_quote(quote_id)):
                raise InvalidRequestException("Invalid Quote")

            return service_id, quote_id
        else:
            logger.debug("[basic_quote_validation] Provided invalid confirmation hash!")
            raise UnauthorizedException("Invalid token!")
