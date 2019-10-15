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

# mqtt
DEFAULT_MIN_TIMEOUT = 0.5
DEFAULT_MAX_TIMEOUT = 2

# tcp
DEFAULT_CONNECTION_TIMEOUT = 60
DEFAULT_THREAD_POOL_LIMIT = 10
DEFAULT_DATA_LENGTH = 1024

MANAGER_SCOPE = 'manager'
APPLICATION_SCOPE = 'application'

# Access variables
ACCESS_NO_POWER = 'no_power'
ACCESS_DISCONNECTED = 'disconnected'
ACCESS_UNREACHABLE_VALUE = 'unreachable'
ACCESS_REMOTE_CONTROL_DISABLED = 'remote_control_disabled'
ACCESS_PERMISSION_REVOKED = 'permission_revoked'
ACCESS_SERVICE_ERROR_VALUE = 'service_error'  # this retry reading the property
ACCESS_UNAUTHORIZED_VALUE = 'unauthorized'  # this shows a blue
ACCESS_API_UNREACHABLE = 'api_unreachable'
ACCESS_NOK_VALUE = 'nok'
ACCESS_CONNECTED = 'connected'
ACCESS_OK_VALUE = 'ok'

HEARTBEAT_PROP = 'heartbeat'
