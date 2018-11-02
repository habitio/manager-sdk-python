import json


def format_response(resp):
    """
    Returns a str formatted response
    :param resp: Requests response
    :return: response text as a string, formatted as a json if valid
    """
    try:
        error_msg = format_str(resp.json(), is_json=True)
    except ValueError:  # requests returns a ValueError when resp.text is not a valid json
        error_msg = format_str(resp.text, is_json=False)
    return error_msg

def format_str(str_value, is_json):
    """
    Returns a formatted string with break lines; if is_json True, pretty format the output
    :param str_value: plain text or json value
    :param is_json: Boolean
    :return: str
    """
    str_value = json.dumps(str_value, indent=4, sort_keys=True) if is_json else str_value
    return '\n {} \n'.format(str_value)


def is_json(str_value):
    """A function to check if a string contains a valid json"""
    try:
        json.loads(str_value)
    except ValueError:
        return False
    return True
