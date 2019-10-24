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


class WebhookHubApplication(WebhookHubBase):

    def __init__(self, queue=None, implementer=None):
        super().__init__(queue, implementer)
        self.patch_quotesimulate()
        application = self.get_application()
        if "confirmation_hash" in application:
            self.confirmation_hash = application['confirmation_hash']
            logger.notice("Confirmation Hash : {}".format(self.confirmation_hash))

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
                            "url": _service["url"]
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

                    logger.debug("Initiated PATCH - {}".format(_service['url']))
                    logger.verbose("\n{}\n".format(json.dumps(data, indent=4, sort_keys=True)))

                    resp = requests.patch('{}/services/{}'.format(settings.api_server_full, _service['id']),
                                          data=json.dumps(data), headers=self.session.headers)

                    logger.verbose("Received response code[{}]".format(resp.status_code))
                    logger.verbose("\n{}\n".format(json.dumps(resp.json(), indent=4, sort_keys=True)))

                    if int(resp.status_code) == 200:
                        logger.notice("Service setup successful!")
                    else:
                        raise Exception('Service setup not successful!')

                except Exception as ex:

                    logger.alert("Failed to set service!\n{}".format(ex))
                    os._exit(1)

        except Exception as e:
            logger.alert("Failed at patch endpoints! {}".format(traceback.format_exc(limit=5)))
            raise

    @retry(wait=wait_fixed(DEFAULT_RETRY_WAIT))
    def patch_quotesimulate(self):
        try:
            url = settings.webhook_url
            data = {
                'quotesimulate_uri': f'{settings.schema_pub}://{settings.host_pub}/'
                                     f'{settings.api_version}/quote-simulate'
            }

            logger.debug(f"Initiated PATCH - {url}")
            logger.verbose("\n{}\n".format(json.dumps(data, indent=4, sort_keys=True)))

            resp = requests.patch(url, data=json.dumps(data), headers=self.session.headers)

            logger.verbose("Received response code[{}]".format(resp.status_code))
            logger.verbose("\n{}\n".format(json.dumps(resp.json(), indent=4, sort_keys=True)))

            if int(resp.status_code) == 200:
                logger.notice("Quote simulate setup successful!")
            else:
                raise Exception('Quote simulate setup not successful!')

        except Exception as e:
            logger.alert("Failed at patch quote simulate! {}".format(traceback.format_exc(limit=5)))
            raise

    @retry(wait=wait_fixed(DEFAULT_RETRY_WAIT))
    def get_application(self):
        try:
            logger.debug(f"Trying to get application data - {settings.webhook_url}")
            resp = requests.get(settings.webhook_url, headers=self.session.headers)
            logger.verbose("Received response code[{}]".format(resp.status_code))

            if int(resp.status_code) == 200:
                logger.notice("Get application successful!")
                return resp.json()
            else:
                raise Exception('Error getting application!')

        except Exception as e:
            logger.alert("Failed while get application! {}".format(traceback.format_exc(limit=5)))
            raise


    def webhook_registration(self):
        try:
            if self.watchdog_monitor:
                self.watchdog_monitor.start() if self.watchdog_monitor.thread is None else \
                    logger.notice("Watchdog thread alive? : {}".format(self.watchdog_monitor.thread.is_alive()))

            self.implementer.start()

        except Exception as e:
            logger.alert("Unexpected exception {}".format(traceback.format_exc(limit=5)))
            os._exit(1)
