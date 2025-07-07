# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2025 Valory AG
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

"""This module contains utility functions and classes for the mech interact abci skill."""

import json
from dataclasses import asdict, is_dataclass
from typing import Any


class DataclassEncoder(json.JSONEncoder):
    """A custom JSON encoder for dataclasses."""

    def default(self, o: Any) -> Any:
        """The default JSON encoder."""
        if is_dataclass(o) and not isinstance(o, type):
            result = asdict(o)
            # Ensure important fields are preserved even if they have default values
            if hasattr(o, "requestId") and o.requestId != 0:
                result["requestId"] = o.requestId
            if hasattr(o, "result") and o.result is not None:
                result["result"] = o.result
            return result
        return super().default(o)
