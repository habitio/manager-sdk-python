from flask import request, Response
from base.common.router_base import RouterBase
from base import settings, logger


class RouterApplication(RouterBase):

    def activate(self):
        return self.webhook.activate(request)

    def service_authorize(self):
        return self.webhook.service_authorize(request)

    def route_setup(self, app):
        logger.debug("App {}".format(app))
        super().route_setup(app)

        app.add_url_rule('/', view_func=self.starter, methods=['GET'])
        app.add_url_rule("/{}/receive-token".format(settings.api_version), view_func=self.receive_token, methods=['POST'])

        for _service in settings.services:
            app.add_url_rule("/{}/services/{}/authorize".format(settings.api_version, _service['id']),
                             view_func=self.service_authorize, methods=['GET', 'POST'])

        app.add_url_rule("/{}/users/activate".format(settings.api_version), view_func=self.activate, methods=['POST'])
        app.add_url_rule("/{}/inbox".format(settings.api_version), view_func=self.inbox, methods=['POST'])

        app.after_request_funcs.setdefault(app.name, []).append(self.after)
