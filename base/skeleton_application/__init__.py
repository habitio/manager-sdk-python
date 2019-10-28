from base.common.skeleton_base import SkeletonBase
from base.utils import format_response
from .router import *
from .webhook import *

NAMESPACES_FILTER = ['rate_chunk', 'rate_base']
VALID_QUOTE_STATES = ['draft', 'open', 'simulated', 'closed']
QUOTE_URI = "%s/applications/%s/quotes/{quote_id}" % (settings.api_server_full, settings.client_id)
QUOTE_PROPERTIES_URI = "%s/properties" % QUOTE_URI


class SkeletonApplication(SkeletonBase):

    @property
    def platform_header(self):
        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        }

    def _check_quote(self, quote_id):
        # Check if quote exists
        _url = QUOTE_URI.format(quote_id=quote_id)
        self.log(f"Try to get quote: {_url}", 7)
        resp = requests.get(url=_url, headers=self.platform_header)
        if resp.status_code != 200:
            raise InvalidRequestException("Invalid quote")

    def _get_properties_by_quote(self, quote_id):
        _url = QUOTE_PROPERTIES_URI.format(quote_id=quote_id)
        _params = {
            "namespace": f"in/{NAMESPACES_FILTER}/j"
        }
        self.log(f"Try to get properties: {_url}", 7)
        resp = requests.get(url=_url, headers=self.platform_header, params=_params)
        if resp.status_code != 200:
            raise InvalidRequestException("Invalid quote")
        properties = resp.json().get('elements', [])
        self.log(f"Properties found: {properties}", 7)

        return properties

    def _patch_property(self, quote_id, property_id, data):
        self.log(f"Patch property: {property_id}; Data: {data}", 7)
        url = f"{QUOTE_PROPERTIES_URI.format(quote_id=quote_id)}/{property_id}"

        # PATCH property
        resp = requests.patch(url=url, headers=self.platform_header, json=data)
        if not resp or resp.status_code != 200:
            raise ValidationException(f"[PATCH_PROPERTY]Error while patching property quote: {quote_id}; "
                                      f"property: {property_id}; data: {data}; Response: {format_response(resp)}")

        # GET property
        resp = requests.get(url=url, headers=self.platform_header)
        if not resp or resp.status_code != 200:
            raise ValidationException(f"[PATCH_PROPERTY]Error while get updated property: {quote_id}; "
                                      f"property: {property_id}; data: {data}; Response: {format_response(resp)}")

        return resp.json()

    def _patch_quote(self, quote_id, data):
        self.log(f"Patch quote: {quote_id}; Data: {data}", 7)
        url = QUOTE_URI.format(quote_id=quote_id)

        # PATCH quote
        resp = requests.patch(url=url, headers=self.platform_header, json=data)
        if not resp or resp.status_code != 200:
            raise ValidationException(f"[PATCH_QUOTE]Error while patching quote: {quote_id}; "
                                      f"data: {data}; Response: {format_response(resp)}")

        # GET quote
        resp = requests.get(url=url, headers=self.platform_header)
        if not resp or resp.status_code != 200:
            raise ValidationException(f"[PATCH_QUOTE]Error while get updated quote: {quote_id}; "
                                      f"data: {data}; Response: {format_response(resp)}")

        return resp.json()

    def update_quote_state(self, quote_id, state: str):
        state = state.lower()
        if state not in VALID_QUOTE_STATES:
            logger.error(f"Invalid quote state: {state}")
            raise ValidationException(f"Invalid quote state: {state}")

        data = {'state': 'simulated'}
        quote = self._patch_quote(quote_id, data)
        return quote

    def quote_simulate(self, service_id, quote_id):
        """
        Invoked when application receives a quote_simulate call

        Receives:
            service_id - unique service id. Must be set in configuration file
            quote_id - UUID of quote

        Returns:
            {
                "quote_properties": [
                    {
                        "data" : ":data",
                        "id" : ":uuid",
                        "namespace": ":namespace"
                    },
                    ...

                ],
                "coverage_properties": [
                    {
                        "data" : ":data",
                        "coverage_id": ":uuid",
                        "id" : ":uuid",
                        "namespace": ":namespace"
                    },
                    ...
                ]
            }
        """
        raise NotImplementedError('No polling handler implemented')


SkeletonBase.register(SkeletonApplication)
