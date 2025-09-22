# # -*- coding: utf-8 -*-
# # ------------------------------------------------------------------------------
# #
# #   Copyright 2023-2025 Valory AG
# #
# #   Licensed under the Apache License, Version 2.0 (the "License");
# #   you may not use this file except in compliance with the License.
# #   You may obtain a copy of the License at
# #
# #       http://www.apache.org/licenses/LICENSE-2.0
# #
# #   Unless required by applicable law or agreed to in writing, software
# #   distributed under the License is distributed on an "AS IS" BASIS,
# #   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# #   See the License for the specific language governing permissions and
# #   limitations under the License.
# #
# # ------------------------------------------------------------------------------

# """This package contains round behaviours of decision making."""

# import datetime
# from dataclasses import dataclass
# from pathlib import Path
# from typing import Any, Dict, Optional, Type, cast

# from packages.valory.skills.abstract_round_abci.base import AbciAppDB
# from packages.valory.skills.abstract_round_abci.behaviour_utils import (
#     make_degenerate_behaviour,
# )
# from packages.valory.skills.abstract_round_abci.test_tools.base import (
#     FSMBehaviourBaseCase,
# )
# from packages.valory.skills.decision_making_abci.behaviours import (
#     DecisionMakingBehaviour,
# )
# from packages.valory.skills.decision_making_abci.models import SharedState
# from packages.valory.skills.decision_making_abci.rounds import (
#     Event,
#     FinishedDecisionMakingDBLoadRound,
#     FinishedDecisionMakingLLMRound,
#     FinishedDecisionMakingUpdateCentaurRound,
#     FinishedDecisionMakingWriteOrbisRound,
#     FinishedDecisionMakingWriteTwitterRound,
#     SynchronizedData,
# )
# from packages.valory.skills.decision_making_abci.tests import centaur_configs


# DUMMY_CENTAURS_DATA = [
#     centaur_configs.ENABLED_CENTAUR,
#     centaur_configs.DISABLED_CENTAUR,
# ]


# @dataclass
# class BehaviourTestCase:
#     """BehaviourTestCase"""

#     name: str
#     initial_data: Dict[str, Any]
#     next_behaviour_class: Optional[Type[DecisionMakingBehaviour]] = None


# class BaseDecisionMakingTest(FSMBehaviourBaseCase):
#     """Base test case."""

#     path_to_skill = Path(__file__).parent.parent

#     behaviour: DecisionMakingBehaviour  # type: ignore
#     behaviour_class: Type[DecisionMakingBehaviour]
#     next_behaviour_class: Type[DecisionMakingBehaviour]
#     synchronized_data: SynchronizedData
#     done_event = Event.DONE
#     centaur_id_to_secrets = centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_OK

#     def fast_forward(self, data: Optional[Dict[str, Any]] = None) -> None:
#         """Fast-forward on initialization"""

#         data = data if data is not None else {}
#         self.fast_forward_to_behaviour(
#             self.behaviour,  # type: ignore
#             self.behaviour_class.auto_behaviour_id(),
#             SynchronizedData(AbciAppDB(setup_data=AbciAppDB.data_to_lists(data))),
#         )
#         assert (
#             self.behaviour.current_behaviour.auto_behaviour_id()  # type: ignore
#             == self.behaviour_class.auto_behaviour_id()
#         )

#     def complete(self, event: Event) -> None:
#         """Complete test"""

#         self.behaviour.act_wrapper()
#         self.mock_a2a_transaction()
#         self._test_done_flag_set()
#         self.end_round(done_event=event)
#         assert (
#             self.behaviour.current_behaviour.auto_behaviour_id()  # type: ignore
#             == self.next_behaviour_class.auto_behaviour_id()
#         )

#     def mock_params(self, centaur_id_to_secrets) -> None:
#         """Update skill params."""
#         self.skill.skill_context.params.__dict__.update({"_frozen": False})
#         self.skill.skill_context.params.centaur_id_to_secrets = centaur_id_to_secrets


# class BaseDecisionMakingBehaviourTest(BaseDecisionMakingTest):
#     """Tests DecisionMakingBehaviour"""

#     behaviour_class = DecisionMakingBehaviour
#     next_behaviour_class: Type[DecisionMakingBehaviour]

#     def test_run(self) -> None:
#         """Run tests."""
#         self.mock_params(self.centaur_id_to_secrets)  # type: ignore
#         state = cast(SharedState, self._skill.skill_context.state)
#         state.round_sequence._last_round_transition_timestamp = datetime.datetime.now()
#         state.ceramic_data = DUMMY_CENTAURS_DATA
#         self.fast_forward(self.initial_data)  # type: ignore
#         for _ in range(5):  # Needed due to the amount of nested generators
#             self.behaviour.act_wrapper()

#         self.complete(self.event)  # type: ignore


# class TestDecisionMakingBehaviourReadCentaurs(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": None,
#         "centaurs_data": [],
#     }
#     event = Event.READ_CENTAURS
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingDBLoadRound
#     )


# class TestDecisionMakingBehaviourLLM(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.READ_CENTAURS.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#     }
#     event = Event.LLM
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingLLMRound
#     )


# class TestDecisionMakingBehaviourDailyTweet(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.LLM.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#         "llm_results": ["My awesome tweet"],
#     }
#     event = Event.DAILY_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourRepromptingA(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.LLM.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#         "llm_results": ["My awesome tweet" * 50],  # tweet too long
#     }
#     event = Event.DAILY_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourRepromptingB(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.LLM.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#         "llm_results": ["My awesome tweet" * 50],  # tweet too long
#         "re_prompt_attempts": 3,
#     }
#     event = Event.DAILY_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourDailyTweetBadConfigA(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     centaur_id_to_secrets = centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_TWITTER
#     initial_data = {
#         "previous_decision_event": Event.LLM.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#         "llm_results": ["My awesome tweet"],
#     }
#     event = Event.DAILY_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourDailyTweetBadConfigB(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     centaur_id_to_secrets = (
#         centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_TWITTER_KEY
#     )
#     initial_data = {
#         "previous_decision_event": Event.LLM.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#         "llm_results": ["My awesome tweet"],
#     }
#     event = Event.DAILY_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourDailyTweetNoTimeToRun(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.LLM.value,
#         "centaurs_data": [centaur_configs.NO_TIME_TO_RUN],
#         "llm_results": ["My awesome tweet"],
#     }
#     event = Event.DAILY_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourDailyTweetAlreadyRan(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.LLM.value,
#         "centaurs_data": [centaur_configs.ALREADY_RAN],
#         "llm_results": ["My awesome tweet"],
#     }
#     event = Event.DAILY_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourDailyOrbis(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.DAILY_TWEET.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#         "daily_tweet": ["My awesome tweet"],
#         "tweet_ids": ["tweet_id"],
#     }
#     event = Event.DAILY_ORBIS
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteOrbisRound
#     )


# class TestDecisionMakingBehaviourDailyOrbisBadConfigA(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     centaur_id_to_secrets = centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ID
#     initial_data = {
#         "previous_decision_event": Event.DAILY_TWEET.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#         "daily_tweet": ["My awesome tweet"],
#         "tweet_ids": ["tweet_id"],
#     }
#     event = Event.DAILY_ORBIS
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteOrbisRound
#     )


# class TestDecisionMakingBehaviourDailyOrbisBadConfigB(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     centaur_id_to_secrets = centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ORBIS
#     initial_data = {
#         "previous_decision_event": Event.DAILY_TWEET.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#         "daily_tweet": ["My awesome tweet"],
#         "tweet_ids": ["tweet_id"],
#     }
#     event = Event.DAILY_ORBIS
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteOrbisRound
#     )


# class TestDecisionMakingBehaviourDailyOrbisBadConfigC(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     centaur_id_to_secrets = (
#         centaur_configs.DUMMY_CENTAUR_ID_TO_SECRETS_MISSING_ORBIS_KEY
#     )
#     initial_data = {
#         "previous_decision_event": Event.DAILY_TWEET.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#         "daily_tweet": ["My awesome tweet"],
#         "tweet_ids": ["tweet_id"],
#     }
#     event = Event.DAILY_ORBIS
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteOrbisRound
#     )


# class TestDecisionMakingBehaviourScheduledTweet(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.DAILY_ORBIS.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#         "write_results": [{"stream_id": "dummy_stream_id"}],
#     }
#     event = Event.SCHEDULED_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourScheduledTweetBadConfigA(
#     BaseDecisionMakingBehaviourTest
# ):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.DAILY_ORBIS.value,
#         "centaurs_data": [centaur_configs.MISSING_DAILY_TWEET_CONFIG_CENTAUR_A],
#         "write_results": [{"stream_id": "dummy_stream_id"}],
#     }
#     event = Event.SCHEDULED_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourScheduledTweetBadConfigB(
#     BaseDecisionMakingBehaviourTest
# ):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.DAILY_ORBIS.value,
#         "centaurs_data": [centaur_configs.MISSING_DAILY_TWEET_CONFIG_CENTAUR_B],
#         "write_results": [{"stream_id": "dummy_stream_id"}],
#     }
#     event = Event.SCHEDULED_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourScheduledTweetBadConfigC(
#     BaseDecisionMakingBehaviourTest
# ):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.DAILY_ORBIS.value,
#         "centaurs_data": [centaur_configs.MISSING_DAILY_TWEET_CONFIG_CENTAUR_C],
#         "write_results": [{"stream_id": "dummy_stream_id"}],
#     }
#     event = Event.SCHEDULED_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourScheduledTweetNoPendingTweets(
#     BaseDecisionMakingBehaviourTest
# ):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.DAILY_ORBIS.value,
#         "centaurs_data": [centaur_configs.NO_PENDING_TWEETS],
#         "write_results": [{"stream_id": "dummy_stream_id"}],
#     }
#     event = Event.SCHEDULED_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourScheduledTweetNoActions(
#     BaseDecisionMakingBehaviourTest
# ):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.DAILY_ORBIS.value,
#         "centaurs_data": [centaur_configs.NO_ACTIONS],
#         "write_results": [{"stream_id": "dummy_stream_id"}],
#     }
#     event = Event.SCHEDULED_TWEET
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingWriteTwitterRound
#     )


# class TestDecisionMakingBehaviourUpdateCentaurs(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.SCHEDULED_TWEET.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#         "tweet_ids": ["tweet_id"],
#     }
#     event = Event.UPDATE_CENTAURS
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingUpdateCentaurRound
#     )


# class TestDecisionMakingBehaviourUpdateCentaursNoPendingTweets(
#     BaseDecisionMakingBehaviourTest
# ):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.SCHEDULED_TWEET.value,
#         "centaurs_data": [centaur_configs.NO_PENDING_TWEETS],
#         "tweet_ids": ["tweet_id"],
#     }
#     event = Event.UPDATE_CENTAURS
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingUpdateCentaurRound
#     )


# class TestDecisionMakingBehaviourUpdateCentaursNoActions(
#     BaseDecisionMakingBehaviourTest
# ):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.SCHEDULED_TWEET.value,
#         "centaurs_data": [centaur_configs.NO_ACTIONS],
#         "tweet_ids": ["tweet_id"],
#     }
#     event = Event.UPDATE_CENTAURS
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingUpdateCentaurRound
#     )


# class TestDecisionMakingBehaviourNextCentaurA(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.UPDATE_CENTAURS.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#     }
#     event = Event.LLM
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingLLMRound
#     )


# class TestDecisionMakingBehaviourNextCentaurB(BaseDecisionMakingBehaviourTest):
#     """Behaviour test"""

#     initial_data = {
#         "previous_decision_event": Event.NEXT_CENTAUR.value,
#         "centaurs_data": DUMMY_CENTAURS_DATA,
#         "current_centaur_index": 1,
#     }
#     event = Event.LLM
#     next_behaviour_class = make_degenerate_behaviour(  # type: ignore
#         FinishedDecisionMakingLLMRound
#     )
