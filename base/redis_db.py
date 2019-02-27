import ast
import json
import logging
import traceback

from redis import Redis

from base.settings import settings

logger = logging.getLogger(__name__)


class DBManager(Redis):

    def set_key(self, key, value):
        """
        To set a key-field in hash table
            key : key of the field
            value : content of field
            add_reverse : stores another value-key combination in hash to 
                facilitate search by value inexpensively.

        """
        try:
            self.hset(settings.redis_db, key, value)

            logger.debug("[DB] Key {} added/updated in database".format(key))
        except Exception as e:
            logger.error("[DB] Failed to set the key at hash. {}".format(traceback.format_exc(limit=5)))

    def has_key(self, key):
        try:
            result = self.hexists(settings.redis_db, key)
            return result == 1
        except Exception as e:
            logger.error("[DB] Failed to check if hash has key. {}".format(traceback.format_exc(limit=5)))

    def get_key(self, key):
        """To get a key"s field from hash table"""
        try:
            if self.hexists(settings.redis_db, key):
                value = self.hget(settings.redis_db, key)
                logger.debug("[DB]  Key {} retrieved from database.".format(key))
                try:
                    evaluated_value = ast.literal_eval(value)
                except Exception as e:
                    evaluated_value = value
                return evaluated_value
            else:
                logger.warning("[DB] Key {} not found in database.".format(key))
        except Exception as e:
            logger.error("[DB] get_key error, {}".format(traceback.format_exc(limit=5)))

    def query(self, regex):
        logger.debug("[DB] query regex={}".format(regex))

        results = []
        try:
            for element in self.hscan_iter(settings.redis_db, match=regex):
                str_element = element[1].replace('\'', '\"')
                try:
                    value = json.loads(str_element)
                except ValueError:
                    value = str_element

                results.append(value)

            logger.debug("[DB] Query found {} results!".format(len(results)))
            return results
        except Exception as e:
            logger.error("[DB] query :: {}".format(e, traceback.format_exc(limit=5)))

    def full_query(self, regex):
        logger.debug("[DB] full query regex={}".format(regex))

        results = []
        try:
            for element in self.hscan_iter(settings.redis_db, match=regex):
                str_element = element[1].replace('\'', '\"')
                try:
                    value = json.loads(str_element)
                except ValueError:
                    value = str_element

                results.append({
                    'key': element[0],
                    'value': value
                })

            logger.debug("[DB] Full Query found {} results!".format(len(results)))
            return results
        except Exception as e:
            logger.error("[DB] full query :: {}".format(e, traceback.format_exc(limit=5)))

    def clear_hash(self):
        try:
            self.delete(settings.redis_db)
            logger.notice("[DB] Redis database shutdown.")
        except Exception as e:
            logger.error("[DB] Failed to clear redis database, {}".format(traceback.format_exc(limit=5)))

    def save_n_exit(self):
        """ To safely exit the opened client """
        try:
            self.shutdown()
            logger.notice("[DB]  Redis database shutdown.")
        except Exception as e:
            logger.error("[DB] Failed to shutdown redis database, {}".format(traceback.format_exc(limit=5)))

    def __get_credentials_old(self, client_id, owner_id, channel_id):
        '''
            Due to legacy code, this method retrieves credentials stored just by uuid
        '''

        logger.info("[DB] No credentials found w/ new format! Search w/ old format")

        result = db.get_key(owner_id)
        if not result:
            result = db.get_key("/".join([client_id, owner_id]))

        if result:
            self.set_credentials(result, client_id, owner_id, channel_id)

        return result

    def get_credentials_with_key(self, client_id, owner_id, channel_id=None):
        data = None
        credentials_key = None

        if channel_id:
            credentials_key = "/".join(
                ['credential-clients', client_id, 'owners', owner_id, 'channels', channel_id])
            data = db.query(credentials_key)
            if not data:
                credentials_key = "/".join(
                    ['credential-owners', owner_id, 'channels', channel_id])
                data = db.query(credentials_key)

        if not data:
            credentials_key = "/".join(
                ['credential-clients', client_id, 'owners', owner_id])
            data = db.query(credentials_key)
            if not data:
                data = self.__get_credentials_old(
                    client_id, owner_id, channel_id)
                if not data:
                    logger.warning("[DB] No credentials found!")
                    return None
                else:
                    data = [data]
            elif channel_id:
                self.set_credentials(data[0], owner_id, channel_id)

        credentials = data[0]

        logger.debug("[DB] Credentials Found! {}".format(credentials_key))

        return credentials, credentials_key

    def get_credentials(self, client_id, owner_id, channel_id=None, with_key=False):
        credentials, key = self.get_credentials_with_key(client_id, owner_id, channel_id)

        if with_key:  # to include credential key used
            return credentials, key

        return credentials


    def set_credentials(self, credentials, client_id, owner_id, channel_id=None):
        if not client_id or not owner_id:
            raise Exception("[DB] Not enough keys (client or owner missing)")
        else:
            credentials['client_id'] = client_id
            credentials_key = "/".join(['credential-clients',
                                        client_id, 'owners', owner_id])

            if channel_id:
                credentials_key = "/".join(['credential-owners',
                                            owner_id, 'channels', channel_id])

            db.set_key(credentials_key, credentials)

    def get_device_id(self, channel_id):
        key = "/".join(['device-channels', channel_id])
        data = db.query(key)

        if not data:
            logger.info("[DB] No device found w/ new format! Search w/ old format")
            key = channel_id
            result = db.get_key(key)

            if not result:
                logger.warning("[DB] No device found for channel {}".format(key))
                return None
            else:
                self.set_device_id(channel_id, result, True)
        else:
            result = data[0]

        return result

    def set_device_id(self, channel_id, device_id, add_reverse=False):
        key = "/".join(['device-channels', channel_id])
        db.set_key(key, device_id)

        if add_reverse:
            self.set_channel_id(device_id, channel_id)

    def get_channel_id(self, device_id):
        key = "/".join(['channel-devices', device_id])
        data = db.query(key)

        if not data:
            logger.info("[DB] No channel found w/ new format! Search w/ old format")
            key = device_id
            result = db.get_key(key)

            if not result:
                logger.warning("[DB] No channel found for device {}".format(key))
                return None
            else:
                self.set_channel_id(device_id, result, True)
        else:
            result = data[0]

        return result

    def set_channel_id(self, device_id, channel_id, add_reverse=False):
        key = "/".join(['channel-devices', device_id])
        db.set_key(key, channel_id)

        if add_reverse:
            self.set_device_id(channel_id, device_id)

    def get_channel_status(self, channel_id):
        key = "/".join(['status-channels', channel_id])

        data = db.query(key)

        if not data:
            logger.warning("[DB] No status found for channel {}".format(key))
            return None

        return data[0]

    def set_channel_status(self, channel_id, status):
        key = "/".join(['status-channels', channel_id])
        db.set_key(key, status)

    def expire(self, key, time):
        logger.warning("[DB] To be implemented!")

    def get_channels(self, device_id=None):
        if not device_id : device_id = '*'
        return list(set(db.query('channel-devices/{}'.format(device_id))))    

try:
    db = DBManager(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True
    )

    logger.info("[DB] Successfully connected Redis-client to Redis-server")
except Exception as e:
    logger.error("[DB] Failed to connect Redis-client to Redis server, {}".format(traceback.format_exc(limit=5)))
