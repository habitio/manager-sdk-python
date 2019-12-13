from base.thread_pool import pool_task
from base import settings, logger
# from base.solid import get_implementer
from .token_refresher import TokenRefresherManager


@pool_task
def handle_credentials(credentials, old_credentials, client_id, owner_id, channel_id, ignore_keys=None):
    from base.solid import implementer
    refresher = TokenRefresherManager(implementer=implementer)
    ignore_keys = ignore_keys or []

    logger.debug("\n\n\n\n\n\t\t\t\t\t*******************HANDLE_CREDENTIALS****************************")
    logger.info(f"Client_id {client_id}; Owner_id: {owner_id}; channel_id: {channel_id}")
    if settings.config_refresh.get('enabled') is True:
        if not channel_id:
            logger.warning(f"[handle_credentials] channel_id not set: {channel_id}")
            return
        elif 'refresh_token' not in old_credentials:
            logger.error("[handle_credentials] Refresh token not found in old credentials")
            return
        else:
            updated_cred = []
            updated_cred.extend(ignore_keys)
            refresh_token = old_credentials['refresh_token']
            credentials_list = refresher.get_credentials_by_refresh_token(refresh_token) or []
            # remove updated keys from credentials list
            credentials_list = [cred_ for cred_ in credentials_list if cred_['key'] not in ignore_keys]

            logger.verbose(f"[handle_credentials] Starting update by token_refresher for channel: {channel_id}")
            updated_, error_keys = refresher.update_credentials(credentials, credentials_list)
            ignore_keys.extend(updated_)
            ignore_keys.extend(error_keys)
            updated_cred.extend(updated_)

            logger.debug(f"[handle_credentials] Starting update all owners for channel: {channel_id}")
            updated_, error_keys = refresher.update_all_owners(credentials, channel_id, ignore_keys)
            ignore_keys.extend(updated_)
            ignore_keys.extend(error_keys)
            updated_cred.extend(updated_)

            logger.debug("[handle_credentials] Starting update all channels")
            updated_cred.extend(refresher.update_all_channels(credentials, owner_id, ignore_keys))

            logger.debug(f"[handle_credentials] Updated keys: {list(set(updated_cred))}")

            del refresher.channel_relations