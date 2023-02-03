# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2022-2023 Valory AG
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

"""This package contains tools for the DynamicNFTAbciApp."""


SHEET_API_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "required": ["spreadsheetId", "valueRanges"],
    "properties": {
        "spreadsheetId": {"type": "string"},
        "valueRanges": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {
                "type": "object",
                "required": [
                    "range",
                    "majorDimension",
                    "values",
                ],
                "properties": {
                    "range": {"type": "string"},
                    "majorDimension": {"type": "string"},
                    "values": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "string",
                                "minItems": 1,
                            },
                        },
                    },
                },
            },
        },
    },
}
