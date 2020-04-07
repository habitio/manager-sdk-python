import requests
import traceback
from base.common.skeleton_base import SkeletonBase
from base.exceptions import InvalidRequestException, ValidationException, ChannelNotFound
from base.utils import format_response, is_valid_uuid
from base.constants import QUOTE_PROPERTIES_URI, QUOTE_URI, COVERAGES_URI
from .router import *
from .webhook import WebhookHubApplication


class SkeletonApplication(SkeletonBase):

    @property
    def platform_header(self):
        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(settings.block["access_token"])
        }

    def get_quote(self, quote_id: str) -> dict:
        self.log(f"Get quote: {quote_id}", 7)
        _url = QUOTE_URI.format(api_server_full=settings.api_server_full, client_id=settings.client_id,
                                quote_id=quote_id)

        self.log(f"Try to get quote: {_url}", 7)
        resp = requests.get(url=_url, headers=self.platform_header)
        if resp.status_code != 200:
            raise InvalidRequestException("get_quote: Invalid quote")
        quote = resp.json()
        self.log(f"Quote found: {len(quote)}", 7)

        return quote

    def get_properties_by_quote(self, quote_id: str, params: dict = None):
        params = params or {}
        # get properties using quote_id
        _url = QUOTE_PROPERTIES_URI.format(api_server_full=settings.api_server_full, client_id=settings.client_id,
                                           quote_id=quote_id)

        self.log(f"Try to get properties: {_url}", 7)
        resp = requests.get(url=_url, headers=self.platform_header, params=params)
        if resp.status_code != 200:
            raise InvalidRequestException("get_properties_by_quote: Invalid quote")
        properties = resp.json().get('elements', [])
        self.log(f"Properties found: {len(properties)}", 7)

        return properties

    def get_quotes_by_properties(self, entity: str, properties_filters: list) -> list:
        url = f"{settings.api_server_full}/applications/{settings.client_id}/find-quotes-by-properties"
        quotes = []
        try:
            if not (entity and properties_filters):
                return quotes
            if type(properties_filters) is not list:
                properties_filters = [properties_filters]

            json = {
                'entity': entity,
                'properties': {
                    'filters': properties_filters
                }
            }
            resp = requests.post(url, headers=self.header, json=json)

            if int(resp.status_code) == 200:
                quotes = resp.json()['elements']
            elif int(resp.status_code) == 204:  # No content
                logger.verbose(f"[get_quotes_by_properties] Received response code[{resp.status_code}]")
            else:
                logger.verbose(f"[get_quotes_by_properties] Received response code[{resp.status_code}]")
                raise ChannelNotFound(f"[get_quotes_by_properties] Failed to retrieve quotes for entity: {entity}; "
                                      f"filters: {properties_filters}")

        except (OSError, ChannelNotFound) as e:
            logger.warning('[get_quotes_by_properties] Error while making request to platform: {}'.format(e))
        except Exception:
            logger.alert("[get_quotes_by_properties] Unexpected error: {}".format(traceback.format_exc(limit=5)))
        return quotes

    def get_coverages_by_quote(self, quote_id: str, params: dict = None) -> list:
        params = params or {}
        # get properties using quote_id
        _url = COVERAGES_URI.format(api_server_full=settings.api_server_full, client_id=settings.client_id,
                                    quote_id=quote_id)

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

    def get_coverage_properties(self, quote_id: str, coverage_id: str, params: dict = None) -> list:
        params = params or {}
        # get properties using quote_id
        _url = COVERAGES_URI.format(api_server_full=settings.api_server_full, client_id=settings.client_id,
                                    quote_id=quote_id) + f"/{coverage_id}/properties"

        self.log(f"Try to get coverage properties: {_url}", 7)
        resp = requests.get(url=_url, headers=self.platform_header, params=params)
        if resp.status_code not in [200, 204]:
            raise InvalidRequestException("get_coverage_properties: Invalid quote or coverage")

        if resp.status_code == 200:
            properties = resp.json().get('elements', [])
            self.log(f"Coverage properties found: {len(properties)}", 7)
        else:
            properties = []
            self.log("Coverage properties not found", 7)

        return properties

    def protected_asset_search(self, namespace: str, quote_id: str) -> list:
        url = f"{settings.api_server_full}/applications/{settings.client_id}/protected-assets-search"
        _protected_assets = []
        try:
            if not namespace:
                return _protected_assets

            json = {
                "properties": {
                    "filters": [
                        {
                            "namespace": namespace,
                            "type": "equals",
                            "data": quote_id
                        }
                    ]

                },
                "page_start_index": 0,
                "page_size": 1
            }

            resp = requests.post(url, headers=self.header, json=json)

            if int(resp.status_code) == 200:
                _protected_assets = resp.json()['elements']
            elif int(resp.status_code) == 204:  # No content
                self.log(f"[protected_asset_search] Received response code[{resp.status_code}]", 9)
            else:
                self.log(f"[protected_asset_search] Received response code[{resp.status_code}]", 9)
                raise ChannelNotFound(f"[protected_asset_search] Failed to retrieve protected asset for quote: {quote_id}; ")

        except (OSError, ChannelNotFound) as e:
            self.log('[protected_asset_search] Error while making request to platform: {}'.format(e), 4)
        except Exception:
            self.log("[protected_asset_search] Unexpected error: {}".format(traceback.format_exc(limit=5)), 5)
        return _protected_assets

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
        url = QUOTE_PROPERTIES_URI.format(api_server_full=settings.api_server_full, client_id=settings.client_id,
                                          quote_id=quote_id) + f"/{property_id}"

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
        url = COVERAGES_URI.format(api_server_full=settings.api_server_full, client_id=settings.client_id,
                                   quote_id=quote_id) + f"/{coverage_id}/properties/{property_id}"

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
        url = QUOTE_URI.format(api_server_full=settings.api_server_full, client_id=settings.client_id,
                               quote_id=quote_id)

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
        """
        raise NotImplementedError('No quote simulate implemented')

    def quote_setup(self, service_id: str, quote_id: str):
        """
        Invoked when application receives a quote_setup call

        Receives:
            service_id - unique service id. Must be set in configuration file
            quote_id - UUID of quote
        """
        return NotImplementedError('No quote setup implemented')

    def quote_checkout(self, service_id: str, quote_id: str):
        """
        Invoked when application receives a quote_checkout call

        Receives:
            service_id - unique service id. Must be set in configuration file
            quote_id - UUID of quote
        """
        raise NotImplementedError('No quote checkout implemented')

    def get_channel_by_owner(self, owner_id, channel_id):
        """
        Input :
            owner_id
            channel_id

        Returns channeltemplate_id

        """

        url = "{}/users/{}/channels?channel_id={}".format(settings.api_server_full, owner_id, channel_id)

        try:
            resp = requests.get(url, headers=self.header)

            if int(resp.status_code) == 200:
                return resp.json()['elements'][0]['channel']
            elif int(resp.status_code) == 204:  # No content
                logger.verbose("[get_channel_by_owner] Received response code[{}]".format(resp.status_code))
                return False
            else:
                logger.verbose("[get_channel_by_owner] Received response code[{}]".format(resp.status_code))
                raise ChannelNotFound(f"[get_channel_by_owner] Failed to retrieve channel for {channel_id}")

        except (OSError, ChannelNotFound) as e:
            logger.warning('[get_channel_by_owner] Error while making request to platform: {}'.format(e))
        except Exception:
            logger.alert("[get_channel_by_owner] Unexpected error: {}".format(traceback.format_exc(limit=5)))
        return ''

    def get_cards_by_owner(self, owner_id: str, **kwargs) -> list:
        url = f"{settings.api_server_full}/users/{owner_id}/cards"
        if 'page_size' not in kwargs:
            kwargs['page_size'] = 20

        try:
            resp = requests.get(url, headers=self.header, params=kwargs)

            if int(resp.status_code) == 200:
                return resp.json()['elements']
            elif int(resp.status_code) == 204:  # No content
                logger.verbose("[get_cards_by_owner] Received response code[{}]".format(resp.status_code))
                return []
            else:
                logger.verbose("[get_cards_by_owner] Received response code[{}]".format(resp.status_code))
                raise InvalidRequestException(f"[get_channel_by_owner] Failed to retrieve cards for {owner_id}")

        except (OSError, InvalidRequestException) as e:
            logger.warning('[get_channel_by_owner] Error while making request to platform: {}'.format(e))
        except Exception:
            logger.alert("[get_channel_by_owner] Unexpected error: {}".format(traceback.format_exc(limit=5)))
        return []

SkeletonBase.register(SkeletonApplication)
