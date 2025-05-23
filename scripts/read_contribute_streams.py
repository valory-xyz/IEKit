# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021-2025 Valory AG
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

"""This package contains code to read Contribute streams on Ceramic."""
# pylint: disable=import-error

import json
import os

import dotenv
from ceramic.ceramic import Ceramic
from ceramic.streams import (
    CONTRIBUTE_PROD_CENTAURS_STREAM_ID,
    CONTRIBUTE_PROD_DB_STREAM_ID,
    CONTRIBUTE_PROD_MANUAL_STREAM_ID,
)


dotenv.load_dotenv(override=True)

def main():
    """Main"""
    ceramic = Ceramic(os.getenv("CERAMIC_API_BASE"))

    # Users db
    db, _, _ = ceramic.get_data(CONTRIBUTE_PROD_DB_STREAM_ID)
    with open("contribute_db.json", "w", encoding="utf-8") as of:
        json.dump(db, of, indent=4)
        print("Contribute DB written to contribute_db.json")

    # Centaurs db
    centaurs, _, _ = ceramic.get_data(CONTRIBUTE_PROD_CENTAURS_STREAM_ID)
    with open("contribute_centaurs.json", "w", encoding="utf-8") as of:
        json.dump(centaurs, of, indent=4)
        print("Centaurs DB written to contribute_centaurs.json")

    # Manual point db
    points, _, _ = ceramic.get_data(CONTRIBUTE_PROD_MANUAL_STREAM_ID)
    with open("contribute_generic_points.json", "w", encoding="utf-8") as of:
        json.dump(points, of, indent=4)
        print("Manual DB written to contribute_generic_points.json")


if __name__ == "__main__":
    main()
