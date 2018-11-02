from flask import request, Response, json
from base import auth
from base import logger
from base.mqtt_connector import mqtt
from base.webhook_handler import webhook
from base.settings import settings
from base.utils import format_str


class Views:

    def __init__(self, _app):
        self.route_setup(_app)
        self.kickoff()

    def kickoff(self):
        '''
        Setting up manager before it starts serving

        '''
        logger.verbose("Starting sdk with a kickoff ...")

        auth.get_access()
        if settings.block["access_token"] != "":
            mqtt.mqtt_config()
            webhook.webhook_registration()

    def route_setup(self, app):
        logger.debug("App {}".format(app))

        @app.route("/")
        def starter():
            return Response(status=200)

        @app.route("/{api_version}/authorize".format(api_version=settings.api_version), methods=["GET"])
        def authorize():
            return webhook.authorize(request)

        @app.route("/{api_version}/receive_token".format(api_version=settings.api_version), methods=["POST"])
        def receive_token():
            return webhook.receive_token(request)

        @app.route("/{api_version}/devices_list".format(api_version=settings.api_version), methods=["POST"])
        def devices_list():
            return webhook.devices_list(request)

        @app.route("/{api_version}/select_device".format(api_version=settings.api_version), methods=["POST"])
        def select_device():
            return webhook.select_device(request)

        @app.route("/{api_version}/manufacturer".format(api_version=settings.api_version), methods=["POST"])
        def agent():
            webhook.agent(request)
            return Response(
                status=200
            )

        @app.after_request
        def after(response):
            try:
                if "Location" in response.headers:
                    logger.debug("Redirect {} code[{}]".format(response.headers["Location"], response.status))
                else:
                    logger.debug("Responding with status code[{}]".format(response.status))
                if response.mimetype == "application/json":
                    logger.verbose(format_str(json.loads(response.response[0])), is_json=True)
            except:
                logger.error("Post request logging failed !")
            return response
