import requests
import traceback
from base import settings, logger
from base.exceptions import ChannelTemplateNotFound, InvalidRequestException


def validate_channel(channel_id, return_channel=False):
    try:
        header = {
            "Authorization": f"Bearer {settings.block['access_token']}",
            "Accept": "application/json",
        }
        if not channel_id:
            logger.warning(f"get_channel_template :: Invalid channel_id")
            return ''
        url = f"{settings.api_server_full}/channels/{channel_id}"

        resp = requests.get(url, headers=header)

        if int(resp.status_code) == 200:
            return resp.json() if return_channel else True
        else:
            logger.verbose(f"[validate_channel] Received response code [{resp.status_code}]")
            raise ChannelTemplateNotFound(f"Failed to retrieve channel_template_id for {channel_id}")

    except (OSError, ChannelTemplateNotFound) as e:
        logger.warning(f'[validate_channel] Error while making request to platform: {e}')
    except Exception as ex:
        logger.alert(f"[validate_channel] Unexpected error get_channel_template: {traceback.format_exc(limit=5)}")
    return False


def validate_quote(quote_id):
    try:
        header = {
            "Authorization": f"Bearer {settings.block['access_token']}",
            "Accept": "application/json",
        }
        if not quote_id:
            logger.warning(f"[validate_quote] Invalid quote_id")
            return False

        url = f"{settings.api_server_full}/applications/{settings.client_id}/quotes/{quote_id}"

        resp = requests.get(url, headers=header)

        if int(resp.status_code) == 200:
            return resp.json()
        else:
            logger.verbose(f"[validate_quote] Received response code [{resp.status_code}]")
            raise InvalidRequestException(f"Failed to retrieve quote for {quote_id}")

    except (OSError, InvalidRequestException) as e:
        logger.warning(f'[validate_quote] Error while making request to platform: {e}')
    except Exception:
        logger.alert(f"[validate_quote] Unexpected error: {traceback.format_exc(limit=5)}")
    return False
