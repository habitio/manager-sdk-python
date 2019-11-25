from base.common.skeleton_base import SkeletonBase
from base.utils import format_response
from .router import *
from .webhook import *

QUOTE_URI = "%s/applications/%s/quotes/{quote_id}" % (settings.api_server_full, settings.client_id)
QUOTE_PROPERTIES_URI = "%s/properties" % QUOTE_URI
COVERAGES_URI = "%s/coverages" % QUOTE_URI


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
            raise InvalidRequestException("_check_quote: Invalid quote")

    def get_properties_by_quote(self, quote_id, params=None):
        params = params or {}
        # get properties using quote_id
        _url = QUOTE_PROPERTIES_URI.format(quote_id=quote_id)

        self.log(f"Try to get properties: {_url}", 7)
        resp = requests.get(url=_url, headers=self.platform_header, params=params)
        if resp.status_code != 200:
            raise InvalidRequestException("get_properties_by_quote: Invalid quote")
        properties = resp.json().get('elements', [])
        self.log(f"Properties found: {len(properties)}", 7)

        return properties

    def get_coverages_by_quote(self, quote_id, params=None):
        params = params or {}
        # get properties using quote_id
        _url = COVERAGES_URI.format(quote_id=quote_id)

        self.log(f"Try to get properties: {_url}", 7)
        resp = requests.get(url=_url, headers=self.platform_header, params=params)
        if resp.status_code not in [200, 204]:
            raise InvalidRequestException("get_coverages_by_quote: Invalid quote")

        if resp.status_code == 200:
            coverages = resp.json().get('elements', [])
            self.log(f"Coverages found: {len(coverages)}", 7)
        else:
            coverages = []
            self.log("Coverages not found", 7)

        return coverages

    def get_coverage_properties(self, quote_id, coverage_id, params=None):
        params = params or {}
        # get properties using quote_id
        _url = f"{COVERAGES_URI.format(quote_id=quote_id)}/{coverage_id}/properties"

        self.log(f"Try to get coverage properties: {_url}", 7)
        resp = requests.get(url=_url, headers=self.platform_header, params=params)
        if resp.status_code not in [200, 204]:
            raise InvalidRequestException("get_coverage_properties: Invalid quote or coverage")

        if resp.status_code == 200:
            properties = resp.json().get('elements', [])
            self.log(f"Coverages found: {len(properties)}", 7)
        else:
            properties = []
            self.log("Coverages not found", 7)

        return properties

    def _patch_property(self, quote_id: str, property_id: str, data: dict, return_property: bool = False) -> dict:
        """
        Make PATCH request to update quote/<quote_id>/properties/<property_id>
        :param quote_id: UUID
        :param property_id: UUID
        :param data: Dict - Payload to be patched to property
        :param return_property: bool - True return full updated property / False return just patch response
        :return: Dict with full updated property or PATCH response
        """
        self.log(f"Patch property: {property_id}; Data: {data}", 7)
        url = f"{QUOTE_PROPERTIES_URI.format(quote_id=quote_id)}/{property_id}"

        # PATCH property
        resp = requests.patch(url=url, headers=self.platform_header, json=data)
        if not resp or resp.status_code != 200:
            raise ValidationException(f"[PATCH_PROPERTY]Error while patching property quote: {quote_id}; "
                                      f"property: {property_id}; data: {data}; Response: {format_response(resp)}")

        # GET property
        if return_property:
            resp = requests.get(url=url, headers=self.platform_header)
            if not resp or resp.status_code != 200:
                raise ValidationException(f"[PATCH_PROPERTY]Error while get updated property: {quote_id}; "
                                          f"property: {property_id}; data: {data}; Response: {format_response(resp)}")

        return resp.json()

    def _patch_coverage_property(self, quote_id: str, coverage_id: str, property_id: str, data: dict,
                                 return_property: bool = False) -> dict:
        """
        Make PATCH request to update quote/<quote_id>/properties/<property_id>
        :param quote_id: UUID
        :param coverage_id: UUID
        :param property_id: UUID
        :param data: Dict - Payload to be patched to property
        :param return_property: bool - True return full updated property / False return just patch response
        :return: Dict with full updated property or PATCH response
        """
        self.log(f"Patch coverage: {coverage_id}; property: {property_id}; Data: {data}", 7)
        url = f"{COVERAGES_URI.format(quote_id=quote_id)}/{coverage_id}/properties/{property_id}"

        # PATCH property
        resp = requests.patch(url=url, headers=self.platform_header, json=data)
        if not resp or resp.status_code != 200:
            raise ValidationException(f"[PATCH_COVERAGE_PROPERTY]Error while patching property quote: {quote_id}; "
                                      f"coverage: {coverage_id}; property: {property_id}; data: {data}; "
                                      f"Response: {format_response(resp)}")

        # GET property
        if return_property:
            resp = requests.get(url=url, headers=self.platform_header)
            if not resp or resp.status_code != 200:
                raise ValidationException(f"[PATCH_COVERAGE_PROPERTY]Error while get updated property: {quote_id}; "
                                          f"coverage: {coverage_id}; property: {property_id}; data: {data}; "
                                          f"Response: {format_response(resp)}")

        return resp.json()

    def _patch_quote(self, quote_id: str, data: dict, return_quote: bool = False) -> dict:
        """
        Make PATCH request to update quote/<quote_id>
        :param quote_id: UUID
        :param data: Dict - Payload to be patched to property
        :param return_quote: bool - True return full updated property / False return just patch response
        :return: Dict with full updated quote or PATCH response
        """
        self.log(f"Patch quote: {quote_id}; Data: {data}", 7)
        url = QUOTE_URI.format(quote_id=quote_id)

        # PATCH quote
        resp = requests.patch(url=url, headers=self.platform_header, json=data)
        if not resp or resp.status_code != 200:
            raise ValidationException(f"[PATCH_QUOTE]Error while patching quote: {quote_id}; "
                                      f"data: {data}; Response: {format_response(resp)}")

        if return_quote:
            # GET quote
            resp = requests.get(url=url, headers=self.platform_header)
            if not resp or resp.status_code != 200:
                raise ValidationException(f"[PATCH_QUOTE]Error while get updated quote: {quote_id}; "
                                          f"data: {data}; Response: {format_response(resp)}")

        return resp.json()

    def update_quote_state(self, quote_id: str, state: str, return_quote: bool, **kwargs):
        """
        Update quote state according to received state
        :param quote_id: UUID
        :param state: str from list VALID_QUOTE_STATES
        :param return_quote: bool - True return full updated quote / False return just patch response
        :return:
        """
        state = state.lower()

        data = {'state': state}
        data.update(kwargs)
        quote = self._patch_quote(quote_id, data, return_quote)
        return quote

    def update_quote_property(self, quote_id: str, property_id: str, payload: dict,
                              return_property: bool) -> dict:
        """
        Update quote property data according to received value
        :param quote_id: UUID
        :param property_id: UUID
        :param payload: dict -> payload data to update
        :param return_property: bool - True return full updated quote property /
                                       False return True if Patched
        """
        self.log(f"Update property value for {property_id}; With payload: {payload}", 7)
        if not (is_valid_uuid(quote_id) and is_valid_uuid(property_id)):
            raise ValidationException(f"[update_quote_property] Invalid quote or property")

        # try to patch property with new data
        new_property = self._patch_property(quote_id, property_id, payload, return_property)

        return new_property if return_property else True

    def update_quote_coverage_property(self, quote_id: str, coverage_id: str, property_id: str, new_value: str,
                                       return_property: bool) -> dict:
        """
        Update quote property data according to received value
        :param quote_id: UUID
        :param coverage_id: UUID
        :param property_id: UUID
        :param new_value: str -> new value to property data
        :param return_property: bool - True return full updated quote property /
                                       False return True if Patched
        """

        self.log(f"Update quote coverage property value for {property_id}; New value: {new_value}", 7)

        if not (is_valid_uuid(quote_id) and is_valid_uuid(coverage_id) and is_valid_uuid(property_id)):
            raise ValidationException(f"[update_quote_property] Invalid quote, coverage or property")

        data = {
            'data': new_value
        }
        # try to patch property with new data
        new_property = self._patch_coverage_property(quote_id, coverage_id, property_id, data, return_property)

        return new_property if return_property else True

    def quote_simulate(self, service_id: str, quote_id: str):
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
                        "id" : ":uuid",
                        "namespace": ":namespace",
                        "coverage_id": ":uuid",
                        "coverage": {
                            "id": ":uuid",
                            "namespace": ":namespace"
                        }
                    },
                    ...
                ]
            }
        """
        raise NotImplementedError('No quote simulate implemented')

    def quote_customize(self, service_id: str, quote_id: str):
        """
        Invoked when application receives a quote_customize call

        Receives:
            service_id - unique service id. Must be set in configuration file
            quote_id - UUID of quote

        Returns:
            list of modified properties
            [
                {
                    "data" : ":data",
                    "id" : ":uuid",
                    "namespace": ":namespace"
                },
                ...

            ]
        """
        return []


SkeletonBase.register(SkeletonApplication)
