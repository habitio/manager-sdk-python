from flask import Response, jsonify
import logging, traceback

from base.redis_db import db
from base.settings import settings
from base.mqtt_connector import mqtt
from base.utils import format_str

logger = logging.getLogger(__name__)

class WebhookHubBase:

    def __init__(self):
        from base.solid import implementer
        self.implementer = implementer
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        }

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

    def inbox(self, request):

        logger.debug("\n\n\n\n\n\t\t\t\t\t*******************INBOX****************************")
        logger.debug("Received {} - {}".format(request.method, request.path))
        logger.verbose("\n{}".format(request.headers))

        if request.is_json:
            logger.verbose(format_str(request.get_json(), is_json=True))
        else:
            logger.verbose("\n{}".format(request.get_data(as_text=True)))

        downstream_tuple = self.implementer.downstream(request)

        try:
            case = downstream_tuple[0]
            data = downstream_tuple[1]
            if case and data:
                mqtt.publisher(io="iw", data=data, case=case)
        except (TypeError, KeyError):
            logger.debug('downstream method returned {}'.format(downstream_tuple))

        status_code = 200
        try:
            response = downstream_tuple[2]
            if type(response) is dict:  # status and data keys are mandatory
                status_code = response['status']
                response_data = jsonify(response['data'])
                return response_data, status_code
            else:
                status_code = int(response)
        except (IndexError, TypeError) as e:
            logger.info('Custom response data not found. {}'.format(e))

        return Response(status=status_code)
