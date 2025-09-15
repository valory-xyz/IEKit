# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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

"""Test the models.py module of the ScoreRead."""
from datetime import datetime

import pytest

from packages.valory.skills.abstract_round_abci.test_tools.base import DummyContext
from packages.valory.skills.abstract_round_abci.tests.test_models import (
    BASE_DUMMY_PARAMS,
)
from packages.valory.skills.twitter_scoring_abci.models import (
    OpenAICalls,
    Params,
    SharedState,
)


class TestSharedState:
    """Test SharedState of ScoreRead."""

    def test_initialization(self) -> None:
        """Test initialization."""
        SharedState(name="", skill_context=DummyContext())


class TestOpenAICalls:
    """Test OpanAICalls of TwitterScoringAbci."""

    start_time = datetime.now().timestamp()
    dummy_current_time = start_time + 2.0

    def setup(self) -> None:
        """Set Up test."""

        self.open_ai_calls = OpenAICalls(
            openai_call_window_size=1.0, openai_calls_allowed_in_window=10
        )
        self.open_ai_calls._call_window_start = self.start_time

    def test_initialization(self) -> None:
        """Test initialization."""
        self.setup()
        assert self.open_ai_calls._calls_made_in_window == 0
        assert self.open_ai_calls._calls_allowed_in_window == 10
        assert self.open_ai_calls._call_window_size == 1.0
        assert self.open_ai_calls._call_window_start == self.start_time

    def test_increase_call_count(self) -> None:
        """Test increase call count."""
        self.open_ai_calls.increase_call_count()
        assert self.open_ai_calls._calls_made_in_window == 1

    def test_has_window_expired(self) -> None:
        """Test has window expired."""
        assert self.open_ai_calls.has_window_expired(self.dummy_current_time) is True

    def test_max_calls_reached(self) -> None:
        """Test max calls reached."""
        self.open_ai_calls._calls_made_in_window = 11
        assert self.open_ai_calls.max_calls_reached() is True

    @pytest.mark.parametrize(
        "mock_current_time, assert_calls_in_window, assert_current_time",
        [
            (start_time + 0.5, 5, start_time),
            (dummy_current_time, 0, dummy_current_time),
        ],
        ids=["window_not_expired", "window_expired"],
    )
    def test_reset(
        self, mock_current_time, assert_calls_in_window, assert_current_time
    ) -> None:
        """Test reset."""
        self.open_ai_calls._calls_made_in_window = 5
        self.open_ai_calls.reset(float(mock_current_time))

        assert self.open_ai_calls._calls_made_in_window == assert_calls_in_window
        assert self.open_ai_calls._call_window_start == assert_current_time


class TestParams:
    """Test Params of OlasWeek."""

    def test_initialization(self) -> None:
        """Test initialization."""
        Params(**BASE_DUMMY_PARAMS)
