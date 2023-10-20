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

"""This package contains LLM prompts for WeekInOlasAbciApp."""

tweet_summarizer_prompt = """
Create a post consisting of 2 lists of concise headlines about the Olas ecosystem this week for each of the tweets in the input section below.
The first list should be just a list of headlines. The second should be the same list of headlines with their accompanying tweet link.
Do not hyperlink. Where possible @mention relevant accounts. Each headline should be output in bullet points, using ☴ as the bullet points.

My input will follow the format:
week number
Tweet1 text
Tweet1 link
Tweet2 text
Tweet2 link
and so on

Your response should follow the format:
"Week [Week number] in Olas
Highlights included:
☴[Tweet1 headline]
☴[Tweet2 headline]
☴[Tweet3 headline]
☴[Tweet4 headline]
☴[Tweet5 headline]
☴[Tweet6 headline]
and so on
☴[Tweet1 headline]
[Tweet1 link]
☴[Tweet2 headline]
[Tweet2 link]
☴[Tweet3 headline]
[Tweet3 link]
☴[Tweet4 headline]
[Tweet4 link]
 ☴[Tweet5 headline]
[Tweet5 link]
☴[Tweet6 headline]
[Tweet6 link]
and so on
Stay tuned for more in Week [week number +1].. :cohete:"

Here is an example:
My input was:
40
Community Build Spotlight: Innovation Station :cohete:
Discover Innovation Station, a double award-winner at
@ETHGlobal
, and your portal to easy, fast decentralized app & multi-agent  service creation.
It is the latest service to receive OLAS top-ups from the ecosystem.
https://twitter.com/autonolas/status/1709964445781565938
Olas is a partner in the
@safe
 DAATA and AI Hackathon from 9 - 16 Oct.
Win bounties for projects at the intersection of DATA, AI and AA, including one for Prediction Agents:bola_de_cristal:
Happy hacking!
More info: https://safe-global.notion.site/DAATA-and-AI-Hackathon-77a70251b20c41bdb3efe80cfcfebf59
:apuntando_hacia_la_derecha: Sign up here:
https://twitter.com/autonolas/status/1709936581505884234
AIP-1 Approved!
The OLAS Triple Lock proposal targets pivotal enhancements in bonding, dev rewards, and OLAS staking.
Immediate next steps: propelling OLAS onto
@gnosischain
 to fortify liquidity and prepare for staking.
https://twitter.com/autonolas/status/1709240423959740440
1/ $OLAS has the most potential since $ETH.
It isn't another VC chain, dApp, or memecoin.
It's the first system that unifies blockchain & AI; two trends set to define the century.
This thread will get you up to speed on
@autonolas
 current and future use cases.
https://twitter.com/DistilledCrypto/status/1708830436879741341
Data unions will use and will be enabled by co-owned AI technologies
@autonolas
 $OLAS
This is my own take of a super interesting conversation between
@LawrenceLundy
 and
@shivmalik
 on the future and viability of data unions.
https://twitter.com/Valorianxyz/status/1708900741304422633
This is intended to be an
@autonolas
 mega-thread.
Genesis begins.
Enjoy!
$OLAS
https://twitter.com/PPLSOPTIMISMCEO/status/1708190863631753531
Attention, Agent Hackers! :mega:
Join us for an exclusive workshop next week, hosted by The Graph ecosystem (
@graphprotocol
).
:calendario_de_sobremesa: Thursday 12/10
:reloj_de_alarma: 1pm UTC
:tachuela_redonda:https://discord.com/events/899649805582737479/1158346575437901874
Boost your project and overall skills with web3 data querying!
https://twitter.com/autonolas/status/1710294338435957248"

Your response should have been:
"Week 40 in Olas
Highlights included:
☴ Innovation Station Spotlight: Double Award-Winner at @ETHGlobal
☴ Olas Partners with @safe for DAATA and AI Hackathon
☴ AIP-1 Approved: OLAS to Propel onto @gnosischain
☴ @DistilledCrypto Highlights the Unique Value of $OLAS
☴ Data Unions and Co-owned AI Tech: A Conversation Highlight
☴ @PPLSOPTIMISMCEO Initiates a Mega-thread about @autonolas
☴ Exclusive @graphprotocol Workshop for Agent Hackers
☴ Innovation Station Spotlight: Double Award-Winner at @ETHGlobal
https://twitter.com/autonolas/status/1709964445781565938
☴ Olas Partners with @safe for DAATA and AI Hackathon
https://twitter.com/autonolas/status/1709936581505884234
☴ AIP-1 Approved: OLAS to Propel onto @gnosischain
https://twitter.com/autonolas/status/1709240423959740440
☴ @DistilledCrypto Highlights the Unique Value of $OLAS
https://twitter.com/DistilledCrypto/status/1708830436879741341
☴ Data Unions and Co-owned AI Tech: A Conversation Highlight
https://twitter.com/Valorianxyz/status/1708900741304422633
☴ @PPLSOPTIMISMCEO Initiates a Mega-thread about @autonolas
https://twitter.com/PPLSOPTIMISMCEO/status/1708190863631753531
☴ Exclusive @graphprotocol Workshop for Agent Hackers
https://twitter.com/autonolas/status/1710294338435957248
Stay tuned for more in Week 41... :cohete:"

Here is my input, please use it to output a response following the instructions above:
{tweet_text}
"""
