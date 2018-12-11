import logging

# manufacturer's api request
DEFAULT_RATE_LIMIT = 1  # 1/second
DEFAULT_THREAD_MAX_WORKERS = 2

# polling
DEFAULT_POLLING_INTERVAL = 60  # 60 seconds

# refresh token
DEFAULT_REFRESH_INTERVAL = 60  # 60 seconds
DEFAULT_BEFORE_EXPIRES = 300  # 300 seconds

# Retry connection
DEFAULT_RETRY_WAIT = 2  # 2 seconds

MANAGER_SCOPE = 'manager'
APPLICATION_SCOPE = 'application'

def get_log_table(_file_name):

    logger = logging.getLogger(_file_name)

    return (
        logger,
        {
            0: logger.emergency,
            1: logger.alert,
            2: logger.critical,
            3: logger.error,
            4: logger.warning,
            5: logger.notice,
            6: logger.info,
            7: logger.debug,
            8: logger.trace,
            9: logger.verbose
        }
    )
