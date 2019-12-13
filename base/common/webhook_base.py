from flask import Response, jsonify
import traceback
import requests

from base.redis_db import get_redis
from base import settings, logger
from base.utils import format_str
from .watchdog import Watchdog


class WebhookHubBase:

    def __init__(self, queue=None, implementer=None, thread_pool=None):
        self.implementer = implementer
        self.queue = queue
        self.confirmation_hash = ""
        self.thread_pool = thread_pool

        try:
            self.watchdog_monitor = Watchdog()
        except Exception as e:
            logger.error("Failed to start Watchdog, {} {}".format(e, traceback.format_exc(limit=5)))
            self.watchdog_monitor = None

        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        })

        self.db = get_redis()

    @staticmethod
    def _create_expiration_date(credentials):
        credentials['expiration_date'] = credentials.get('expiration_date', 0)
        credentials['expires_in'] = credentials.get('expires_in', 0)

        return credentials

    def receive_token(self, request):
        logger.debug("\n\n\n\n\n\t\t\t\t\t********************** RECEIVE_TOKEN **************************")
        logger.debug("Received {} - {}".format(request.method, request.path))
        logger.verbose("headers: {}".format(request.headers))
        try:
            received_hash = request.headers.get("Authorization").replace("Bearer ", "")
            if received_hash == self.confirmation_hash:
                if request.is_json:
                    received_data = request.get_json()
                    logger.debug(f'Authorize response data: {received_data}')
                else:
                    return Response(status=422)

                return self.handle_receive_token(received_data, request.headers["X-Client-Id"],
                                                 request.headers["X-Owner-Id"])

            else:
                logger.debug("Provided invalid confirmation hash!")
                return Response(status=403)
        except Exception as e:
            logger.error("Couldn't complete processing request, {}".format(traceback.format_exc(limit=5)))

    def handle_receive_token(self, received_data, client_id, owner_id):
        data = self.implementer.auth_response(received_data)
        data = self._create_expiration_date(data)

        if data:
            self.db.set_credentials(data, client_id, owner_id)
            return Response(status=200)
        else:
            logger.warning("No credentials to be stored!")
            return Response(status=401)

    def inbox(self, request):

        logger.debug("\n\n\n\n\n\t\t\t\t\t*******************INBOX****************************")
        logger.info("Received {} - {}".format(request.method, request.path))
        logger.info("\n{}".format(request.headers))

        if request.is_json:
            logger.info(format_str(request.get_json(), is_json=True))
        else:
            logger.info("\n{}".format(request.get_data(as_text=True)))

        return self.handle_request(request)

    def handle_request(self, request):

        logger.debug("\n\n\n\n\n\t\t\t\t\t*******************HANDLE_REQUEST****************************")
        logger.info(f"Request {request}")

        downstream_result = self.implementer.downstream(request)
        downstream_list = downstream_result if type(downstream_result) == list else [downstream_result]

        for downstream_tuple in downstream_list:

            try:
                case = downstream_tuple[0]
                data = downstream_tuple[1]

                if case is not None and data is not None:
                    try:
                        custom_mqtt = downstream_tuple[3]
                        custom_mqtt.publisher(io="iw", data=data, case=case)
                    except (IndexError, AttributeError):
                        self.queue.put({
                            "io": "iw",
                            "data": data,
                            "case": case
                        })
            except (TypeError, KeyError):
                logger.debug('downstream method returned {}'.format(downstream_tuple))

        status_code = 200

        if type(downstream_result) is tuple:
            try:
                response = downstream_tuple[2]
                if type(response) is dict:  # status and data keys are mandatory
                    status_code = response['status']
                    response_data = jsonify(response.get('data'))
                    return response_data, status_code
                else:
                    status_code = int(response)
            except (IndexError, TypeError) as e:
                logger.info('Custom response data not found. {}'.format(e))
        else:
            logger.info('Custom response disabled for multiple publish properties')

        return Response(status=status_code)
