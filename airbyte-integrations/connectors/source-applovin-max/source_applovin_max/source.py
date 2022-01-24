#
# Copyright (c) 2021 Airbyte, Inc., all rights reserved.
#


import csv
from abc import ABC
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple
from datetime import date, datetime, timedelta
from airbyte_cdk.sources.streams.http.auth import NoAuth
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple, Union
import pendulum

import requests
from airbyte_cdk.logger import AirbyteLogger
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http import HttpStream
from pendulum.tz.timezone import Timezone

APPLOVIN_REPORTS_MAX_DELTA_DAYS=90
APPLOVIN_REVENUE_REPORT_PARAM_FORMAT="csv"

# Simple transformer
def parse_date(date: Any, timezone: Timezone) -> datetime:
    if date and isinstance(date, str):
        return pendulum.parse(date).replace(tzinfo=timezone)
    return date

# Basic full refresh stream
class ApplovinMaxStream(HttpStream, ABC):

    url_base = "http://r.applovin.com"
    primary_key = ["day", "package_name"]

    def __init__(
        self, api_key: str, timezone: str, start_date: Union[date, str] = None, end_date: Union[date, str] = None, granularity: str = None, **kwargs
    ):
        super().__init__(**kwargs)
        self.api_key = api_key
        self.start_date = start_date
        self.end_date = end_date
        self.columns = granularity.get("columns") or "day,package_name,application,platform,store_id,device_type,country,impressions,ad_format,estimated_revenue,ecpm,network,network_placement,max_placement,max_ad_unit"
        self.timezone = pendulum.timezone(timezone)

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        return None

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        params = {
            "api_key": self.api_key,
            "start": self.start_date,
            "end": self.end_date
        }

        return params

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        csv_data = map(lambda x: x.decode("utf-8"), response.iter_lines())
        reader = csv.DictReader(csv_data)

        yield from reader


# Basic incremental stream
class IncrementalApplovinMaxStream(ApplovinMaxStream, ABC):
    state_checkpoint_interval = None

    def get_updated_state(self, current_stream_state: MutableMapping[str, Any], latest_record: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            latest_state = latest_record.get(self.cursor_field)
            current_state = current_stream_state.get(self.cursor_field) or latest_state

            if current_state:
                return {self.cursor_field: max(latest_state, current_state)}
            return {}
        except TypeError as e:
            raise TypeError(
                f"Expected {self.cursor_field} type '{type(current_state).__name__}' but returned type '{type(latest_state).__name__}'."
            ) from e

    def stream_slices(
        self, sync_mode, cursor_field: List[str] = None, stream_state: Mapping[str, Any] = None
    ) -> Iterable[Optional[Mapping[str, any]]]:
        stream_state = stream_state or {}
        cursor_value = stream_state.get(self.cursor_field)
        start_date = self.get_date(parse_date(cursor_value, self.timezone), self.start_date, max)
        return self.chunk_date_range(start_date)

    def get_date(self, cursor_value: Any, default_date: datetime, comparator: Callable[[datetime, datetime], datetime]) -> datetime:
        cursor_value = parse_date(cursor_value or default_date, self.timezone)
        date = comparator(cursor_value, default_date)
        return date

    def chunk_date_range(self, start_date: datetime) -> List[Mapping[str, any]]:
        dates = []
        delta = self.end_date - start_date
        while start_date <= self.end_date:
            dates.append({self.cursor_field: start_date})
            start_date += timedelta(days=1)
        return dates


class RevenueReport(IncrementalApplovinMaxStream):
    cursor_field = "Day"
    response_format = "csv"

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "maxReport"

    def request_params(self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None) -> MutableMapping[str, Any]:
        params = super().request_params(stream_state, stream_slice, next_page_token)
        params["columns"] = self.columns
        params["format"] = APPLOVIN_REVENUE_REPORT_PARAM_FORMAT
        params["start"] = stream_slice.get(self.cursor_field).to_date_string() # TODO: - timedelta(days=XX) to retrieve field
        params["end"] = stream_slice.get(self.cursor_field).to_date_string()

        return params

# Source
class SourceApplovinMax(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        try:
            api_key = config["api_key"]
            dates = pendulum.now("UTC").to_date_string()
            test_url = (
                f"http://r.applovin.com/maxReport?api_key={api_key}&columns=day&format=csv&start={dates}&end={dates}"
            )
            response = requests.request("GET", url=test_url)
            if response.status_code != 200:
                error_message = response.content
                if error_message:
                    return False, f"Error message: {error_message}"
                response.raise_for_status()
        except Exception as e:
            return False, e
        return True, None

    def is_start_date_before_earliest_date(self, start_date, earliest_date):
        if start_date <= earliest_date:
            AirbyteLogger().log("INFO", f"Start date over {APPLOVIN_REPORTS_MAX_DELTA_DAYS} days, using start_date: {earliest_date}")
            return earliest_date

        return start_date

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        config["timezone"] = "UTC"
        timezone = pendulum.timezone("UTC")
        if config.get("granularity").get("option_title") == "Aggregated data":
            earliest_date = pendulum.today(timezone) - timedelta(days=APPLOVIN_REPORTS_MAX_DELTA_DAYS)
            start_date = parse_date(config.get("start_date") or pendulum.today(timezone), timezone)
            config["start_date"] = self.is_start_date_before_earliest_date(start_date, earliest_date)
            config["end_date"] = pendulum.now(timezone)
            AirbyteLogger().log("INFO", f"Using start_date: {config['start_date']}, end_date: {config['end_date']}")
            auth = NoAuth()
            return [
                RevenueReport(authenticator=auth, **config),
            ]
        else:
            return []
