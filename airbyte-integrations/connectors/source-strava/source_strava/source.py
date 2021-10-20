#
# Copyright (c) 2021 Airbyte, Inc., all rights reserved.
#
from abc import ABC
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import requests
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http import HttpStream
from airbyte_cdk.sources.streams.http.requests_native_auth import Oauth2Authenticator
from dateutil import parser


# Basic full refresh stream
class StravaStream(HttpStream, ABC):
    url_base = "https://www.strava.com/api/v3/"

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        return None

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        yield response.json()


# Basic incremental stream
class IncrementalStravaStream(StravaStream, ABC):
    def __init__(self, after, **kwargs):
        super().__init__(**kwargs)
        self.after = parser.parse(after).timestamp()

    per_page = 30  # default strava value
    curr_page = 1

    @property
    def cursor_field(self) -> str:
        return "start_date"

    def get_updated_state(self, current_stream_state: MutableMapping[str, Any], latest_record: Mapping[str, Any]) -> \
            Mapping[str, Any]:
        return {self.cursor_field: max(latest_record.get(self.cursor_field, ""),
                                       current_stream_state.get(self.cursor_field, ""))}

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        if len(response.json()) != 0:
            self.curr_page += 1
            return {'page': self.curr_page}

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None,
            next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        return {"per_page": self.per_page, "page": self.curr_page, "after": self.after}

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        yield from response.json()

    def stream_slices(self, stream_state: Mapping[str, Any] = None, **kwargs) -> Iterable[Optional[Mapping[str, any]]]:
        if stream_state:
            self.after = parser.parse(stream_state.get(self.cursor_field)).timestamp()
        return [{"after": self.after}]


class AthleteStats(StravaStream):
    """
    Returns the activity stats of an athlete. Only includes data from activities set to Everyone visibilty.
    API Docs: https://developers.strava.com/docs/reference/#api-Athletes-getStats
    Endpoint: https://www.strava.com/api/v3/<id>/stats
    """
    primary_key = ""

    def __init__(self, athlete_id: int, **kwargs):
        super().__init__(**kwargs)
        self.athlete_id = athlete_id

    def path(
            self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None
    ) -> str:
        athlete_id = self.athlete_id
        return f"athletes/{athlete_id}/stats"


class Activities(IncrementalStravaStream):
    """
    Returns the activities of an athlete.
    API Docs: https://developers.strava.com/docs/reference/#api-Activities-getLoggedInAthleteActivities
    Endpoint: https://www.strava.com/api/v3/athlete/activities
    """
    primary_key = "id"

    def path(
            self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None,
            next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "athlete/activities"


# Source
class SourceStrava(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        """
        :param config:  the user-input config object conforming to the connector's spec.json
        :param logger:  logger object
        :return Tuple[bool, any]: (True, None) if the input config can be used to connect to the API successfully, (False, error) otherwise.
        """
        try:
            auth = self.getOauth(config)
            _ = auth.get_auth_header()
            return True, None
        except Exception as e:
            return False, repr(e)

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        """
        :param config: A Mapping of the user input configuration as defined in the connector spec.
        """
        auth = self.getOauth(config)
        return [AthleteStats(authenticator=auth, athlete_id=config["athlete_id"]),
                Activities(authenticator=auth, after=config["start_date"])]

    def getOauth(self, config):
        return Oauth2Authenticator(
            token_refresh_endpoint="https://www.strava.com/oauth/token",
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            refresh_token=config["refresh_token"],
            scopes=["read_all", "activity:read_all"])
