from ceramic import Ceramic
import json
import dotenv
import os
from pathlib import Path

dotenv.load_dotenv(override=True)

ceramic = Ceramic(os.getenv("CERAMIC_API_BASE"))
ceramic_did_str = "did:key:" + str(os.getenv("CERAMIC_DID_STR"))
ceramic_did_seed = os.getenv("CERAMIC_DID_SEED")


# Step 1: create the schemas
# --------------------------

# Users db
with open(Path("ceramic", "schemas", "db_stream_schema.json"), "r", encoding="utf-8") as inf:
    schema = json.load(inf)
    stream_id = ceramic.create_stream(
        did=ceramic_did_str,
        did_seed=ceramic_did_seed,
        data=schema,
    )
    print(f"db_stream_schema -> {stream_id}")

# Centaurs db
with open(Path("ceramic", "schemas", "centaurs_stream_schema.json"), "r", encoding="utf-8") as inf:
    schema = json.load(inf)
    stream_id = ceramic.create_stream(
        did=ceramic_did_str,
        did_seed=ceramic_did_seed,
        data=schema,
    )
    print(f"centaurs_stream_schema -> {stream_id}")


# Manual points db
with open(Path("ceramic", "schemas", "generic_points_stream_schema.json"), "r", encoding="utf-8") as inf:
    schema = json.load(inf)
    stream_id = ceramic.create_stream(
        did=ceramic_did_str,
        did_seed=ceramic_did_seed,
        data=schema,
    )
    print(f"generic_points_stream_schema -> {stream_id}")

print("Run 'glaze stream:commits <stream_id>' to get the stream commit")

# Step 2: get the schema commit
# -------------------------
# glaze config:set ceramic-url https://ceramic-valory.hirenodes.io
# glaze stream:commits <stream_id>
