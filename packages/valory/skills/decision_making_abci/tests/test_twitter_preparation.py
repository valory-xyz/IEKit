# # #!/usr/bin/env python3
# # # -*- coding: utf-8 -*-
# # # ------------------------------------------------------------------------------
# # #
# # #   Copyright 2021-2024 Valory AG
# # #
# # #   Licensed under the Apache License, Version 2.0 (the "License");
# # #   you may not use this file except in compliance with the License.
# # #   You may obtain a copy of the License at
# # #
# # #       http://www.apache.org/licenses/LICENSE-2.0
# # #
# # #   Unless required by applicable law or agreed to in writing, software
# # #   distributed under the License is distributed on an "AS IS" BASIS,
# # #   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# # #   See the License for the specific language governing permissions and
# # #   limitations under the License.
# # #
# # # ------------------------------------------------------------------------------

"""Test twitter preparation tasks."""
from copy import copy, deepcopy
from pprint import pprint

import pytest

from packages.valory.skills.decision_making_abci.rounds import Event
from packages.valory.skills.decision_making_abci.tasks.twitter_preparation import (
    DailyTweetPreparation,
    ScheduledTweetPreparation,
    TwitterPreparation,
)
from packages.valory.skills.decision_making_abci.test_tools.tasks import (
    BaseTaskTest,
    NOW_UTC,
    TaskTestCase,
)
from packages.valory.skills.decision_making_abci.tests import centaur_configs


DUMMY_CENTAURS_DATA = [deepcopy(centaur_configs.ENABLED_CENTAUR)]

twitter_action = {
    "actorAddress": "did:key:z6Mkon3Necd6NkkyfoGoHxid2znGc59LU3K7mubaRcFbLfLX",
    "outputUrl": f"https://twitter.com/launchcentaurs/status/dummy_id_1",
    "description": "posted to Twitter",
    "timestamp": NOW_UTC.timestamp(),
}

DUMMY_CENTAURS_DATA_ACTIONS = deepcopy(DUMMY_CENTAURS_DATA)
DUMMY_CENTAURS_DATA_ACTIONS[0]["actions"].append(twitter_action)

DUMMY_CENTAURS_DATA_NO_ACTIONS = [deepcopy(centaur_configs.NO_ACTIONS)]
DUMMY_CENTAURS_DATA_NO_ACTIONS[0]["actions"] = twitter_action

DUMMY_CENTAURS_DATA_ACTIONS_DAILY_TWEET = deepcopy(DUMMY_CENTAURS_DATA_ACTIONS)
DUMMY_CENTAURS_DATA_ACTIONS_DAILY_TWEET[0]["configuration"]["plugins"]["daily_tweet"][
    "last_run"
] = NOW_UTC.strftime("%Y-%m-%d %H:%M:%S %Z")

DUMMY_CENTAURS_DATA_NO_ACTIONS_DAILY_TWEET = deepcopy(DUMMY_CENTAURS_DATA_NO_ACTIONS)
DUMMY_CENTAURS_DATA_NO_ACTIONS_DAILY_TWEET[0]["configuration"]["plugins"][
    "daily_tweet"
]["last_run"] = NOW_UTC.strftime("%Y-%m-%d %H:%M:%S %Z")

DUMMY_CENTAURS_DATA_NO_TWEETS = deepcopy(DUMMY_CENTAURS_DATA)
DUMMY_CENTAURS_DATA_NO_TWEETS[0]["plugins_data"]["scheduled_tweet"]["tweets"] = None

DUMMY_CENTAURS_DATA_ONE_TWEET = deepcopy(DUMMY_CENTAURS_DATA)
DUMMY_CENTAURS_DATA_ONE_TWEET[0]["plugins_data"]["scheduled_tweet"]["tweets"].pop(-1)

DUMMY_CENTAURS_DATA_TWEET_POSTED = deepcopy(DUMMY_CENTAURS_DATA_ONE_TWEET)
DUMMY_CENTAURS_DATA_TWEET_POSTED[0]["plugins_data"]["scheduled_tweet"]["tweets"][0][
    "posted"
] = True

DUMMY_CENTAURS_DATA_NOT_TWEET_PROPOSER_VERIFIED = deepcopy(
    DUMMY_CENTAURS_DATA_ONE_TWEET
)
DUMMY_CENTAURS_DATA_NOT_TWEET_PROPOSER_VERIFIED[0]["plugins_data"]["scheduled_tweet"][
    "tweets"
][0]["proposer"]["verified"] = False

DUMMY_CENTAURS_DATA_NOT_EXECUTION = deepcopy(DUMMY_CENTAURS_DATA_ONE_TWEET)
DUMMY_CENTAURS_DATA_NOT_EXECUTION[0]["plugins_data"]["scheduled_tweet"]["tweets"][0][
    "proposer"
]["verified"] = True
DUMMY_CENTAURS_DATA_NOT_EXECUTION[0]["plugins_data"]["scheduled_tweet"]["tweets"][0][
    "executionAttempts"
] = None

DUMMY_CENTAURS_DATA_EXECUTION_NOT_VERIFIED = deepcopy(DUMMY_CENTAURS_DATA_ONE_TWEET)
DUMMY_CENTAURS_DATA_EXECUTION_NOT_VERIFIED[0]["plugins_data"]["scheduled_tweet"][
    "tweets"
][0]["proposer"]["verified"] = True
DUMMY_CENTAURS_DATA_EXECUTION_NOT_VERIFIED[0]["plugins_data"]["scheduled_tweet"][
    "tweets"
][0]["executionAttempts"] = [{"verified": False}]

DUMMY_CENTAURS_DATA_NO_VOTERS = deepcopy(DUMMY_CENTAURS_DATA_ONE_TWEET)
DUMMY_CENTAURS_DATA_NO_VOTERS[0]["plugins_data"]["scheduled_tweet"]["tweets"][0][
    "proposer"
]["verified"] = True
DUMMY_CENTAURS_DATA_NO_VOTERS[0]["plugins_data"]["scheduled_tweet"]["tweets"][0][
    "executionAttempts"
] = [{"verified": None}]
DUMMY_CENTAURS_DATA_NO_VOTERS[0]["plugins_data"]["scheduled_tweet"]["tweets"][0][
    "voters"
] = None


class BaseTwitterPreparationTest(BaseTaskTest):
    """Base class for TwitterPreparation tests."""

    def get_tweet_test(self, test_case: TaskTestCase):
        self.set_up()
        self.create_task_preparation_object(test_case)
        self.mock_task_preparation_object.synchronized_data.update(
            **{"daily_tweet": {"text": "dummy text"}}
        )
        assert self.mock_task_preparation_object.get_tweet() == {"text": "dummy text"}


class TestTwitterPreparation(BaseTwitterPreparationTest):
    """Test TwitterPreparation."""

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Centaur ID to secrets missing id",
                task_preparation_class=TwitterPreparation,
                exception_message=False,
                initial_data={
                    "centaur_id_to_secrets": deepcopy(
                        centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ID
                    ),
                    "synchronized_data": {"centaurs_data": copy(DUMMY_CENTAURS_DATA)},
                },
            ),
            TaskTestCase(
                name="Centaur ID to secrets missing twitter",
                task_preparation_class=TwitterPreparation,
                exception_message=False,
                initial_data={
                    "centaur_id_to_secrets": copy(
                        centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_TWITTER
                    ),
                    "synchronized_data": {"centaurs_data": copy(DUMMY_CENTAURS_DATA)},
                },
            ),
            TaskTestCase(
                name="Centaur ID to secrets missing twitter key",
                task_preparation_class=TwitterPreparation,
                exception_message=False,
                initial_data={
                    "centaur_id_to_secrets": copy(
                        centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_TWITTER_KEY
                    ),
                    "synchronized_data": {"centaurs_data": DUMMY_CENTAURS_DATA},
                },
            ),
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=TwitterPreparation,
                exception_message=True,
                initial_data={
                    "centaur_id_to_secrets": copy(
                        centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK
                    ),
                    "synchronized_data": {"centaurs_data": copy(DUMMY_CENTAURS_DATA)},
                },
            ),
        ],
    )
    def test_check_extra_conditions(self, test_case: TaskTestCase):
        """Test the check_extra_conditions method."""
        print(f"here: {centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ID}")
        super().check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=TwitterPreparation,
                initial_data={
                    "centaur_id_to_secrets": copy(
                        centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK
                    ),
                    "synchronized_data": {
                        "centaurs_data": copy(DUMMY_CENTAURS_DATA),
                        "tweet_ids": ["dummy_id_1"],
                    },
                },
                exception_message=(
                    {
                        "centaurs_data": DUMMY_CENTAURS_DATA_ACTIONS,
                        "has_centaurs_changes": True,
                    },
                    None,
                ),
            ),
            TaskTestCase(
                name="No actions",
                task_preparation_class=TwitterPreparation,
                initial_data={
                    "centaur_id_to_secrets": copy(
                        centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK
                    ),
                    "synchronized_data": {
                        "centaurs_data": [deepcopy(centaur_configs.NO_ACTIONS)],
                        "tweet_ids": ["dummy_id_1"],
                    },
                },
                exception_message=(
                    {
                        "centaurs_data": DUMMY_CENTAURS_DATA_NO_ACTIONS,
                        "has_centaurs_changes": True,
                    },
                    None,
                ),
            ),
        ],
    )
    def test__post_task(self, test_case: TaskTestCase):
        """Test the _post_task method."""
        super()._post_task_base_test(test_case)

    def get_tweet_test(self, test_case: TaskTestCase):
        self.set_up()
        self.create_task_preparation_object(test_case)
        with pytest.raises(NotImplementedError):
            self.mock_task_preparation_object.get_tweet()

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=TwitterPreparation,
                exception_message=None,
            ),
        ],
    )
    def test_get_tweet(self, test_case: TaskTestCase):
        """Test get_tweet."""
        self.set_up()
        self.create_task_preparation_object(test_case)
        with pytest.raises(NotImplementedError):
            self.mock_task_preparation_object.get_tweet()


class TestDailyTweetPreparation(BaseTwitterPreparationTest):
    """Test DailyTweetPreparation."""

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Centaur ID to secrets missing id",
                task_preparation_class=DailyTweetPreparation,
                exception_message=False,
                initial_data={
                    "centaur_id_to_secrets": deepcopy(
                        centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ID
                    ),
                    "synchronized_data": {"centaurs_data": copy(DUMMY_CENTAURS_DATA)},
                },
            ),
            TaskTestCase(
                name="Centaur ID to secrets missing twitter",
                task_preparation_class=DailyTweetPreparation,
                exception_message=False,
                initial_data={
                    "centaur_id_to_secrets": copy(
                        centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_TWITTER
                    ),
                    "synchronized_data": {"centaurs_data": copy(DUMMY_CENTAURS_DATA)},
                },
            ),
            TaskTestCase(
                name="Centaur ID to secrets missing twitter key",
                task_preparation_class=DailyTweetPreparation,
                exception_message=False,
                initial_data={
                    "centaur_id_to_secrets": copy(
                        centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_TWITTER_KEY
                    ),
                    "synchronized_data": {"centaurs_data": copy(DUMMY_CENTAURS_DATA)},
                },
            ),
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=DailyTweetPreparation,
                exception_message=True,
                initial_data={
                    "centaur_id_to_secrets": copy(
                        centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK
                    ),
                    "synchronized_data": {"centaurs_data": copy(DUMMY_CENTAURS_DATA)},
                },
            ),
        ],
    )
    def test_check_extra_conditions(self, test_case: TaskTestCase):
        """Test the check_extra_conditions method."""
        super().check_extra_conditions_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=DailyTweetPreparation,
                # centaur_id_to_secrets=centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                exception_message=(
                    {
                        "write_data": [
                            {
                                "text": "dummy text",
                                "media_hashes": "dummy media hashes",
                                "credentials": {
                                    "consumer_key": "dummy_consumer_key",
                                    "consumer_secret": "dummy_consumer_secret",
                                    "access_token": "dummy_access_token",
                                    "access_secret": "dummy_access_secret",
                                },
                            }
                        ],
                    },
                    Event.DAILY_TWEET.value,
                ),
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {
                        "centaurs_data": DUMMY_CENTAURS_DATA,
                        "daily_tweet": {
                            "text": "dummy text",
                            "media_hashes": "dummy media hashes",
                        },
                    },
                },
            ),
        ],
    )
    def test__pre_task(self, test_case: TaskTestCase):
        """Test the _pre_task method."""
        super()._pre_task_base_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=DailyTweetPreparation,
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {
                        "centaurs_data": DUMMY_CENTAURS_DATA,
                        "tweet_ids": ["dummy_id_1"],
                    },
                },
                exception_message=(
                    {
                        "centaurs_data": DUMMY_CENTAURS_DATA_ACTIONS_DAILY_TWEET,
                        "has_centaurs_changes": True,
                    },
                    None,
                ),
            ),
            TaskTestCase(
                name="No actions",
                task_preparation_class=DailyTweetPreparation,
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {
                        "centaurs_data": [deepcopy(centaur_configs.NO_ACTIONS)],
                        "tweet_ids": ["dummy_id_1"],
                    },
                },
                exception_message=(
                    {
                        "centaurs_data": DUMMY_CENTAURS_DATA_NO_ACTIONS_DAILY_TWEET,
                        "has_centaurs_changes": True,
                    },
                    None,
                ),
            ),
        ],
    )
    def test__post_task(self, test_case: TaskTestCase):
        """Test the _post_task method."""
        super()._post_task_base_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=DailyTweetPreparation,
                exception_message=None,
            ),
        ],
    )
    def test_get_tweet(self, test_case: TaskTestCase):
        """Test get_tweet."""
        super().get_tweet_test(test_case)


class TestScheduledTweetPreparation(BaseTwitterPreparationTest):
    """Test ScheduledTweetPreparation."""

    def _pre_task_base_test(self, test_case: TaskTestCase):
        """Test the _pre_task_method."""

        self.set_up()
        self.create_task_preparation_object(test_case)
        self.mock_params(test_case)
        self.mock_task_preparation_object.synchronized_data.update(
            **test_case.initial_data["synchronized_data"]
        )
        self.mock_task_preparation_object.pending_tweets = test_case.initial_data[
            "extra_data"
        ]["pending_tweets"]
        self.mock_task_preparation_object.tweets_need_update = test_case.initial_data[
            "extra_data"
        ]["tweets_need_update"]

        self._pre_task_base_test_logic(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy path",
                task_preparation_class=ScheduledTweetPreparation,
                exception_message=(
                    {},
                    None,
                ),
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {"centaurs_data": DUMMY_CENTAURS_DATA},
                    "extra_data": {
                        "tweets_need_update": False,
                        "pending_tweets": False,
                    },
                },
            ),
            TaskTestCase(
                name="Tweets need update",
                task_preparation_class=ScheduledTweetPreparation,
                exception_message=(
                    {
                        "centaurs_data": DUMMY_CENTAURS_DATA_NO_TWEETS,
                        "has_centaurs_changes": True,
                    },
                    Event.FORCE_DB_UPDATE.value,
                ),
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {"centaurs_data": DUMMY_CENTAURS_DATA},
                    "extra_data": {
                        "tweets_need_update": True,
                        "pending_tweets": False,
                    },
                },
            ),
            TaskTestCase(
                name="Pending tweets",
                task_preparation_class=ScheduledTweetPreparation,
                exception_message=(
                    {
                        "write_data": [
                            {
                                "text": "dummy text",
                                "media_hashes": "dummy media hashes",
                                "credentials": {
                                    "consumer_key": "dummy_consumer_key",
                                    "consumer_secret": "dummy_consumer_secret",
                                    "access_token": "dummy_access_token",
                                    "access_secret": "dummy_access_secret",
                                },
                            }
                        ],
                    },
                    Event.SCHEDULED_TWEET.value,
                ),
                initial_data={
                    "centaur_id_to_secrets": centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK,
                    "synchronized_data": {"centaurs_data": DUMMY_CENTAURS_DATA},
                    "extra_data": {
                        "tweets_need_update": False,
                        "pending_tweets": [
                            {"text": "dummy text", "media_hashes": "dummy media hashes"}
                        ],
                    },
                },
            ),
        ],
    )
    def test__pre_task(self, test_case: TaskTestCase):
        """Test the _pre_task method."""
        self._pre_task_base_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Happy Path",
                task_preparation_class=DailyTweetPreparation,
                exception_message=None,
            ),
        ],
    )
    def test_get_tweet(self, test_case: TaskTestCase):
        """Test get_tweet."""
        super().get_tweet_test(test_case)

    @pytest.mark.parametrize(
        "test_case",
        [
            TaskTestCase(
                name="Tweet posted",
                task_preparation_class=ScheduledTweetPreparation,
                initial_data={
                    "synchronized_data": {
                        "centaurs_data": DUMMY_CENTAURS_DATA_TWEET_POSTED,
                    },
                },
                exception_message={
                    "logger_info": "The tweet has been already posted",
                    "message": [],
                },
            ),
            TaskTestCase(
                name="Tweet not proposer verified",
                task_preparation_class=ScheduledTweetPreparation,
                initial_data={
                    "synchronized_data": {
                        "centaurs_data": DUMMY_CENTAURS_DATA_NOT_TWEET_PROPOSER_VERIFIED,
                    },
                },
                exception_message={
                    "logger_info": "The tweet proposer signature is not valid",
                    "message": [],
                },
            ),
            TaskTestCase(
                name="Tweet not marked for execution",
                task_preparation_class=ScheduledTweetPreparation,
                initial_data={
                    "synchronized_data": {
                        "centaurs_data": DUMMY_CENTAURS_DATA_NOT_EXECUTION,
                    },
                },
                exception_message={
                    "logger_info": "The tweet is not marked for execution",
                    "message": [],
                },
            ),
            TaskTestCase(
                name="Tweet execution not verified",
                task_preparation_class=ScheduledTweetPreparation,
                initial_data={
                    "synchronized_data": {
                        "centaurs_data": DUMMY_CENTAURS_DATA_EXECUTION_NOT_VERIFIED,
                    },
                },
                exception_message={
                    "logger_info": "The tweet execution attempt has not been verified",
                    "message": [],
                },
            ),
            TaskTestCase(
                name="Tweet no voters",
                task_preparation_class=ScheduledTweetPreparation,
                initial_data={
                    "synchronized_data": {
                        "centaurs_data": DUMMY_CENTAURS_DATA_NO_VOTERS,
                    },
                },
                exception_message={
                    "logger_info": "The tweet has no voters",
                    "message": [],
                },
            ),
        ],
    )
    def test_get_pending_tweets(self, test_case: TaskTestCase):
        """Test get_pending_tweets."""
        self.set_up()
        self.create_task_preparation_object(test_case)
        pprint(test_case.initial_data["synchronized_data"])
        gen = self.mock_task_preparation_object.get_pending_tweets()

        with pytest.raises(StopIteration) as excinfo:
            next(gen)

        assert str(test_case.exception_message["message"]) in str(excinfo.value)
        self.mock_task_preparation_object.logger.info.assert_called_with(
            test_case.exception_message["logger_info"]
        )
