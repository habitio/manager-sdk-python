from flask import request, Response, json

import logging
logger = logging.getLogger(__name__)


class RoutesBase:

    def __init__(self, webhook):
        super(RoutesBase, self).__init__()
        self.webhook = webhook

    def starter(self):
        return Response(status=200)

    def authorize(self):
        return self.webhook.authorize(request)

    def receive_token(self):
        return self.webhook.receive_token(request)

    def inbox(self):
        return self.webhook.inbox(request)

    def after(self, response):

        try:

            if 'Location' in response.headers:
                logger.debug('Redirect {} code[{}]'.format(response.headers['Location'], response.status))
            else:
                logger.debug('Responding with status code[{}]'.format(response.status))

            if response.mimetype == 'application/json':
                logger.verbose('\n{}\n'.format(json.dumps(json.loads(response.response[0]), indent=4, sort_keys=True)))

        except:

            logger.error('Post request logging failed!')

        return response

