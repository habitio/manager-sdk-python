from flask import request
from base.common.router_base import RouterBase
from base import settings

import logging
logger = logging.getLogger(__name__)

class RouterDevice(RouterBase):

    def devices_list(self):
        return self.webhook.devices_list(request)

    def select_device(self):
        return self.webhook.select_device(request)

    def route_setup(self, app):
        logger.debug("App {}".format(app))

        app.add_url_rule('/', view_func=self.starter, methods=['GET'])
        app.add_url_rule("/{}/authorize".format(settings.api_version), view_func=self.authorize, methods=['GET'])
        app.add_url_rule("/{}/receive-token".format(settings.api_version), view_func=self.receive_token, methods=['POST'])
        app.add_url_rule("/{}/devices-list".format(settings.api_version), view_func=self.devices_list, methods=['POST'])
        app.add_url_rule("/{}/select-device".format(settings.api_version), view_func=self.select_device, methods=['POST'])
        app.add_url_rule("/{}/inbox".format(settings.api_version), view_func=self.inbox, methods=['POST'])
        app.after_request_funcs.setdefault(app.name, []).append(self.after)
