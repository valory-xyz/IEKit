# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This module contains the shared state for the abci skill of TwitterScoringAbciApp."""

from datetime import datetime
from typing import Any

from packages.valory.skills.abstract_round_abci.models import BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.abstract_round_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.twitter_scoring_abci.rounds import TwitterScoringAbciApp


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = TwitterScoringAbciApp


class OpenAICalls:
    """OpenAI call window."""

    def __init__(
        self,
        openai_call_window_size: float,
        openai_calls_allowed_in_window: int,
    ) -> None:
        """Initialize object."""
        self._calls_made_in_window = 0
        self._calls_allowed_in_window = openai_calls_allowed_in_window
        self._call_window_size = openai_call_window_size
        self._call_window_start = datetime.now().timestamp()

    def increase_call_count(self) -> None:
        """Increase call count."""
        self._calls_made_in_window += 1

    def has_window_expired(self, current_time: float) -> bool:
        """Increase tweet count."""
        return current_time > (self._call_window_start + self._call_window_size)

    def max_calls_reached(self) -> bool:
        """Increase tweet count."""
        return self._calls_made_in_window >= self._calls_allowed_in_window

    def reset(self, current_time: float) -> None:
        """Reset the window if required.."""
        if not self.has_window_expired(current_time=current_time):
            return
        self._calls_made_in_window = 0
        self._call_window_start = current_time


class Params(BaseParams):
    """Parameters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the parameters object."""
        self.twitter_api_base = self._ensure("twitter_api_base", kwargs, str)
        self.twitter_api_bearer_token = self._ensure(
            "twitter_api_bearer_token", kwargs, str
        )
        self.twitter_mentions_endpoint = self._ensure(
            "twitter_mentions_endpoint", kwargs, str
        )
        self.twitter_mentions_args = self._ensure("twitter_mentions_args", kwargs, str)
        self.twitter_max_pages = self._ensure("twitter_max_pages", kwargs, int)
        self.twitter_search_endpoint = self._ensure(
            "twitter_search_endpoint", kwargs, str
        )
        self.twitter_search_args = self._ensure("twitter_search_args", kwargs, str)
        self.max_points_per_period = self._ensure("max_points_per_period", kwargs, int)
        self.tweet_evaluation_round_timeout = self._ensure(
            "tweet_evaluation_round_timeout", kwargs, float
        )
        self.openai_call_window_size = self._ensure(
            "openai_call_window_size", kwargs, float
        )
        self.openai_calls_allowed_in_window = self._ensure(
            "openai_calls_allowed_in_window", kwargs, int
        )
        self.openai_calls = OpenAICalls(
            openai_call_window_size=self.openai_call_window_size,
            openai_calls_allowed_in_window=self.openai_calls_allowed_in_window,
        )
        super().__init__(*args, **kwargs)


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool
