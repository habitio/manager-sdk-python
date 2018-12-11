from flask import Response
import logging, json, traceback

from base.redis_db import db
from base.settings import settings
from base.mqtt_connector import mqtt
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

        logger.debug("\n\n\n\n\n\t\t\t\t\t*******************MANUFACTURER****************************")
        logger.debug("Received "+request.method+" - "+request.path)

        logger.verbose("\n"+str(request.headers))

        if request.is_json:
            logger.verbose("\n"+json.dumps(request.get_json(),indent=4, sort_keys=True))
        else:
            logger.verbose("\n"+request.get_data(as_text=True))

        case, data = self.implementer.downstream(request)

        if case:
            mqtt.publisher(io="iw", data=data, case=case)
