import json
import logging
import threading
from datetime import datetime

import requests
from dateutil import parser, tz

from base.settings import settings
from base.utils import format_response

logger = logging.getLogger(__name__)


def get_access():
    '''
    To send authorization request with 0Auth2.0 to Muzzley platform

    '''
    logger.verbose("Trying to authroize with Muzzley...")
    data = {
        "client_id": settings.client_id,
        "client_secret": settings.client_secret,
        "response_type": settings.grant_type,
        "scope": settings.scope,
        "state": "active"
    }
    url = settings.auth_url
    try:
        logger.debug("Initiated POST - {}".format(url))
        resp = requests.post(url, data=data)
        if (resp.status_code == 200):
            logger.notice("Manager succesfully Authorized with Muzzley")
            store_info(resp.json())
            start_refresher()
        else:
            error_msg = format_response(resp)
            raise Exception(error_msg)
    except Exception as e:
        logger.alert("Unexpected error during authorization {}".format(e))
        exit()


def renew_token():
    logger.verbose("Trying to refresh Tokens...")
    url = settings.renew_url
    header = {
        "Content-Type": "application/json"
    }
    data = {
        "client_id": settings.client_id,
        "refresh_token": settings.block['refresh_token'],
        "grant_type": settings.grant_type
    }
    try:
        logger.debug("Initiated POST - {}".format(url))

        resp = requests.get(url, params=data, headers=header)
        if (resp.status_code == 200):
            logger.notice("Manager succesfully performed Token refresh")
            store_info(resp.json())
            start_refresher()
        else:
            error_msg = format_response(resp)
            raise Exception(error_msg)
    except Exception as e:
        logger.alert("Unexpected error during token renewal: {}".format(e))
        exit()


def store_info(resp):
    '''
    Stores the response obtained during authorization with Muzzley in base.Settings.block

    '''
    logger.verbose("Caching authorization response info from Muzzley...")
    if 'access_token' and 'refresh_token' and 'expires' and 'code' and 'endpoints' in resp:
        settings.block['access_token'] = resp['access_token']
        settings.block['refresh_token'] = resp['refresh_token']
        settings.block['expires'] = resp['expires']
        settings.block['code'] = resp['code']
        settings.block['http_ep'] = resp['endpoints']['http']
        settings.block['mqtt_ep'] = resp['endpoints']['mqtt']


def to_display():
    display = {
        "access_token": settings.block['access_token'],
        "refresh_token": settings.block['refresh_token'],
        "http": settings.block['http_ep'],
        "mqtt": settings.block['mqtt_ep']
    }
    return display


def clear_cache():
    settings.block.clear()
    logger.info("Memory cache cleared for security")
    pass

def start_refresher():
    """Refreshes the access token 2 days before expiry"""

    logger.debug('Starting token refresh thread ...')
    try:
        expiry_t = parser.parse(settings.block['expires'])
        current_t = datetime.now(tz.gettz(expiry_t.tzname()))
        time_diff = (expiry_t - current_t).total_seconds()
        refresh_after = time_diff - 86400 * 2

        timer = threading.Timer(refresh_after, renew_token)
        timer.daemon = True
        timer.start()
    except Exception as e:
        logger.critical("Token expiry check - thread failed \n {}".format(e))
        logger.trace(e)
        exit()
