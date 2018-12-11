# Breaking down configuration File here!
import json
import os
import sys
from os import path
from .constants import MANAGER_SCOPE, APPLICATION_SCOPE


class Settings:


    def __init__(self):

        # Loading and Reading from Config file
        self.conf_path = sys.argv[1]

        if path.isfile(self.conf_path):
            with open(self.conf_path) as json_data_file:
                self.config_data = json.load(json_data_file)
        else:
            raise IOError("Configuration file is missing!")

        self.config_boot = self.config_data["boot"][0]
        self.config_log = self.config_data["$log"]
        self.config_cred = self.config_boot["rest"]["credentials"]
        self.config_http = self.config_boot["http"]
        self.config_redis = self.config_boot["redis"]["managers"]
        self.config_modules = self.config_boot["modules"]
        self.config_tls = self.config_boot["tls"]
        self.config_manufacturer = self.config_boot.get("manufacturer", {})
        self.config_polling = self.config_boot.get("polling", {})
        self.config_refresh = self.config_boot.get("token_refresher", {})

        self.client_id = self.config_cred["client_id"]
        self.client_secret = self.config_cred["client_secret"]

        # Muzzley API URI
        self.api_version = self.config_boot["rest"]["version"]  # ex. v3
        self.api_server = self.config_cred["server"]  # ex. https://api.platform.integrations.muzzley.com
        self.api_server_full = "{}/{}".format(self.api_server, self.api_version)  # ex. https://api.platform.integrations.muzzley.com/v3

        # Manager Info Public
        parts = self.config_http["public"].split("://")
        self.schema_pub = parts[0]  # ex. https
        self.host_pub = parts[1]  # ex. fake.integrations.muzzley.com

        # Localhost
        parts = self.config_http["bind"].split(":")
        self.schema_loc = parts[0]  # ex. http
        self.port = int(parts[2])  # ex. 60700
        self.host_bind = parts[1].replace("//", "")  # ex. localhost
        self.host_bind_port = "{}:{}".format(self.host_bind, self.port)  # ex. localhost:60700

        # Muzzley OAuth2.0
        self.grant_type = self.config_cred["grant_type"]
        self.scope = self.config_cred["scope"]

        # All urls
        self.auth_url = "{}{}".format(self.api_server_full, "/auth/authorize")
        self.renew_url = "{}{}".format(self.api_server_full, "/auth/exchange")


        # Logging file path
        if "file" in self.config_log and self.config_log["file"] == "{log_path}":
            parts = self.conf_path.split("/")
            self.log_path = os.path.splitext(parts[len(parts) - 1])[0] + ".log"
        elif "file" in self.config_log and self.config_log["file"] != "":
            self.log_path = self.config_log["file"]
        else:
            self.log_path = "/var/log/syslog"

        # Setting up Redis Database
        self.redis_bind = self.config_redis["bind"]
        self.redis_db = self.config_redis["db"]
        parts = self.redis_bind.split(":")
        self.redis_host = parts[0]  # ex. localhost
        self.redis_port = parts[1]  # ex. 6379

        # Picking out path of module that implements the skeleton
        self.skeleton_path = self.config_modules["skeleton_implementation"]

        # Getting TLS related data
        self.cert_path = self.config_tls["cert"]

        # Access Property
        self.access_property = "access"
        self.access_failed_value = "unreachable"

        # Identify skeleton/implementor type by scope
        parts = self.config_cred["scope"].split(' ')
        if MANAGER_SCOPE in parts:
            self.implementor_type = 'device'
            self.webhook_url = "{}{}{}".format(self.api_server_full, "/managers/", self.client_id)
            self.mqtt_topic = 'managers'
        elif APPLICATION_SCOPE in parts:
            self.implementor_type = 'application'
            self.webhook_url = None
            self.mqtt_topic = 'applications'
        else:
            raise Exception('Error to find the implementor type in credentials, not device or application implementor!')
            exit()

        # Application specific conf
        self.services = self.config_boot.get('services', [])
        self.usecases = self.config_boot.get('usecases', [])
        self.channels_grant_access_to_user = self.config_boot.get('channels_grant_access_to_user', [])

        # The block stores all information obtained my manager through request to platform and
        # to be made available to multiple modules.
        self.block = {
            "access_token": "",
            "refresh_token": "",
            "expires": "",
            "code": "",
            "http_ep": "",
            "mqtt_ep": "",
        }

    def get_config(self):
        return self.config_data


# An instance of Settings class
try:
    settings = Settings()
except Exception as e:
    print('Error: {}'.format(e))
    exit()

