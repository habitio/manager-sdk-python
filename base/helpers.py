import requests
import traceback
from base import settings, logger
from base.exceptions import ChannelTemplateNotFound


def validate_channel(channel_id, return_channel=False):
    try:
        header = {
            "Authorization": "Bearer {0}".format(settings.block["access_token"]),
            "Accept": "application/json",
        }
        if not channel_id:
            logger.warning(f"get_channel_template :: Invalid channel_id")
            return ''
        url = "{}/channels/{}?page_size=9999".format(settings.api_server_full, channel_id)

        resp = requests.get(url, headers=header)
        logger.verbose("Received response code[{}]".format(resp.status_code))

        if int(resp.status_code) == 200:
            return resp.json() if return_channel else True
        else:
            raise ChannelTemplateNotFound("Failed to retrieve channel_template_id for {}".format(channel_id))

    except (OSError, ChannelTemplateNotFound) as e:
        logger.warning('get_channel_template :: Error while making request to platform: {}'.format(e))
    except Exception as ex:
        logger.alert("Unexpected error get_channel_template: {}".format(traceback.format_exc(limit=5)))
    return False
