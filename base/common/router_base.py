from flask import request, Response, json
from base import settings, logger
from base.logger_base import level_runtime


class RouterBase:

    def __init__(self, webhook):
        super(RouterBase, self).__init__()
        self.webhook = webhook

    def starter(self):
        return Response(status=200)

    def authorize(self):
        logger.debug('authorize {} '.format(self.webhook.confirmation_hash))
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

    def level_runtime(self):
        return level_runtime(request)

    def route_setup(self, app):
        app.add_url_rule("/{}/level-runtime".format(settings.api_version), view_func=self.level_runtime,
                         methods=['GET', 'POST'])
        self.webhook.implementer.route_setup(app)
