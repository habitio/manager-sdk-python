# Breaking down configuration File here!
import json
import sys, os
from os import path

class Settings:

# Loading and Reading from Config file
    conf_path = sys.argv[1]
    if path.isfile(conf_path):
        with open(conf_path,"r") as json_data_file:
            config_data = json.load(json_data_file)
    else:
        raise IOError("Configuration file is missing!")
        exit()

    config_boot = config_data["boot"][0]
    config_log = config_data["$log"]
    config_cred = config_boot["rest"]["credentials"]
    config_http = config_boot["http"]
    config_redis = config_boot["redis"]["managers"]
    config_modules = config_boot["modules"]
    config_tls = config_boot["tls"]

    client_id = config_cred["client_id"]
    client_secret = config_cred["client_secret"]

    # Muzzley API URI
    api_version = config_boot["rest"]["version"]                # ex. v3
    api_server = config_cred["server"]              # ex. https://api.platform.integrations.muzzley.com
    api_server_full = api_server + "/" + api_version              # ex. https://api.platform.integrations.muzzley.com/v3

    ## Manager Info
    # Public
    parts = config_http["public"].split("://")
    schema_pub = parts[0]              # ex. https
    host_pub = parts[1]              # ex. fake.integrations.muzzley.com

    # Localhost
    parts = config_http["bind"].split(":")
    schema_loc = parts[0]              # ex. http
    port = int(parts[2])              # ex. 60700
    host_bind = parts[1].replace("//", "")              # ex. localhost
    host_bind_port = host_bind + ":" + str(port)              # ex. localhost:60700

    # Muzzley OAuth2.0
    grant_type = config_cred["grant_type"]
    scope = config_cred["scope"]

    # All urls
    auth_url = api_server_full + "/auth/authorize"
    renew_url = api_server_full + "/auth/exchange"
    webhook_url = api_server_full + "/managers/"+client_id

    # Loggging file path
    if "file" in config_log and config_log["file"] == "{log_path}":
        parts = conf_path.split("/")
        log_path = os.path.splitext(parts[len(parts)-1])[0]+".log"
    elif "file" in config_log and config_log["file"] != "":
        log_path = config_log["file"]
    else:
        log_path = "/var/log/syslog"
    

    #Setting up Redis Database
    redis_bind = config_redis["bind"]
    redis_db = config_redis["db"]
    parts = redis_bind.split(":")              
    redis_host = parts[0]              # ex. localhost
    redis_port = parts[1]              # ex. 6379

    #Picking out path of module that implements the skeleton
    skeleton_path = config_modules["skeleton_implementation"]

    #Getting TLS related data
    cert_path = config_tls["cert"]

    #Access Property#
    access_property = "access"
    access_failed_value = "unreachable"


    #The block stores all information obtained my manager through request to platform and 
    # to be made available to multiple modules.
    block = {
        "access_token" : "",
        "refresh_token" : "",
        "expires" : "",
        "code" : "",
        "http_ep" : "",
        "mqtt_ep" : "",
    }
    def get_config(self):
        return self.config_data
    

#An instanece of Settings class
settings = Settings()
