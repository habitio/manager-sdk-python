from flask import request,Response,json
from base import auth
from base import logger
from base.mqtt_connector import mqtt 
from base.webhook_handler import webhook
from base.settings import settings


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

        @app.route("/"+settings.api_version+"/authorize",methods=["GET"])
        def authorize():
            return webhook.authorize(request)

        @app.route("/"+settings.api_version+"/receive_token",methods=["POST"])
        def receive_token():
            return webhook.receive_token(request)

        @app.route("/"+settings.api_version+"/devices_list",methods=["POST"])
        def devices_list():
            return webhook.devices_list(request)

        @app.route("/"+settings.api_version+"/select_device",methods=["POST"])
        def select_device():
            return webhook.select_device(request)

        @app.route("/"+settings.api_version+"/manufacturer",methods=["POST"])
        def agent():
            webhook.agent(request)
            return Response(
                status=200
            )
                
        @app.after_request
        def after(response):
            try:
                if "Location" in response.headers:
                    logger.debug("Redirect "+response.headers["Location"]+" code["+response.status+"]")
                else:
                    logger.debug("Responding with status code["+response.status+"]") 
                if response.mimetype == "application/json":
                    logger.verbose("\n"+json.dumps(json.loads(response.response[0]),indent=4,sort_keys=True)+"\n")
            except:
                logger.error("Post request logging failed !")
            return response

    
    

