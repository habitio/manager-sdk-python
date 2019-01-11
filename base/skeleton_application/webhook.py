import traceback, json, sys, logging, requests
from tenacity import retry, wait_fixed
from flask import Response

from base.common.webhook_base import WebhookHubBase
from base.settings import settings
from base.constants import DEFAULT_RETRY_WAIT

logger = logging.getLogger(__name__)


class WebhookHubApplication(WebhookHubBase):

    def activate(self, request):

        try:

            return self.implementer.activate(request=request, client_id=settings.client_id, access_token=settings.block['access_token'])

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
                        'activation_uri': '{}://{}/v3/services/{}/authorize'.format(settings.schema_pub, settings.host_pub, _service['id'])
                    }

                    logger.debug("Initiated PATCH - {}".format(_service['url']))
                    logger.verbose("\n{}\n".format(json.dumps(data, indent=4, sort_keys=True)))

                    resp = requests.patch('{}/services/{}'.format(settings.api_server_full, _service['id']), data=json.dumps(data), headers=self.headers)

                    logger.verbose("Received response code[{}]".format(resp.status_code))
                    logger.verbose("\n{}\n".format(json.dumps(resp.json(), indent=4, sort_keys=True)))

                    if int(resp.status_code) == 200:
                        logger.notice("Service setup successful!")
                    else:
                        raise Exception('Service setup not successful!')

                except Exception as ex:

                    logger.alert("Failed to set service!\n{}".format(ex))
                    exit()

        except Exception as e:
            logger.alert("Failed at patch endpoints! {}".format(traceback.format_exc(limit=5)))
            raise

    def webhook_registration(self):
        try:
            self.patch_endpoints()
            self.implementer.start()
            if self.watchdog_monitor:
                self.watchdog_monitor.start()
        except Exception as e:
            logger.alert("Unexpected exception {}".format(traceback.format_exc(limit=5)))
            exit()
