import logging
import ast
from redis import Redis
from base.settings import settings

logger = logging.getLogger(__name__)

class DBManager(Redis):

    def set_key(self,key,value,by_value=False):
        """
        To set a key-field in hash table
            key : key of the field
            value : content of field
            by_value : stores another value-key combination in hash to 
                facilitate search by value inexpensively.
        
        """
        try:
            self.hset(settings.redis_db,key,value)
            if by_value == True:
                self.hset(settings.redis_db,value,key)
            logger.verbose(" Key "+str(key)+" added/updated in database")
        except Exception as ex:
            logger.error("Failed to set the key at hash.")
            logger.trace(ex)

    def has_key(self,key):
        try:
            result = self.hexists(settings.redis_db,key)
            if result == 1:
                return True
            else: 
                return False
        except Exception as ex:
            logger.error("Failed to check if hash has key.")
            logger.trace(ex)

    def get_key(self,key):
        """To get a key"s field from hash table"""
        try:
            if self.hexists(settings.redis_db,key):
                value = self.hget(settings.redis_db,key)
                logger.verbose(" Key "+str(key)+" retrieved from database.")
                try :
                    evaluated_value = ast.literal_eval(value)
                except Expection as e:
                    evaluated_value = value
                return evaluated_value
            else:
                logger.warning("Key "+str(key)+" not found in database.")
        except Exception as ex:
            logger.error(ex)
            logger.trace(ex)
            
    def clear_hash(self):
        try:
            #self.delete(settings.redis_db)
            logger.notice(" Redis database shutdown.")
        except Exception as ex:
            logger.error("Failed to clear redis database")
            logger.trace(ex)
    
    def save_n_exit(self):
        """ To safely exit the opened client """
        try:
            self.shutdown()
            logger.notice(" Redis database shutdown.")
        except Exception as ex:
            logger.error("Failed to shutdown redis database")
            logger.trace(ex)
        

try:
    db = DBManager(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True
    )

    logger.info("Successfully connected Redis-client to Redis-server")
except Exception as ex:
    logger.error("Failed to connect Redis-client to Redis server")
    logger.trace(ex)



