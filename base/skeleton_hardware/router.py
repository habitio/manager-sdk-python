from base.common.router_base import RouterBase
from base.settings import settings

import logging
logger = logging.getLogger(__name__)

class RouterHardware(RouterBase):

    def route_setup(self, app):
        logger.debug("App {}".format(app))

        app.add_url_rule('/', view_func=self.starter, methods=['GET'])
        app.add_url_rule("/{}/inbox".format(settings.api_version), view_func=self.inbox, methods=['POST'])

        app.after_request_funcs.setdefault(app.name, []).append(self.after)
