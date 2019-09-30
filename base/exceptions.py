from flask import jsonify


class ChannelTemplateNotFound(Exception):
    pass


class NoAccessDeviceException(Exception):
    pass


class InvalidAccessCredentialsException(Exception):
    pass


class RemoteControlDisabledException(Exception):
    pass


class PermissionRevokedException(Exception):
    pass


class UnauthorizedException(Exception):
    pass


class InvalidRequestException(Exception):
    pass


class ImplementorTypeNotFoundException(Exception):
    pass


class TCPServerNotFoundException(Exception):
    pass


class TCPWrongMessageException(Exception):
    pass


class ApiConnectionErrorException(Exception):
    pass


class PropertyHistoryNotFoundException(Exception):
    pass


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv


def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response
