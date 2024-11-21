from ceramic import Ceramic
import json
import os
import dotenv

dotenv.load_dotenv(override=True)

ceramic = Ceramic(os.getenv("CERAMIC_API_BASE"))
ceramic_did_str = "did:key:" + str(os.getenv("CERAMIC_DID_STR"))
ceramic_did_seed = os.getenv("CERAMIC_DID_SEED")

stream_id = os.getenv("CERAMIC_DB_STREAM_ID")

# Load from json
with open("stream.json", "r", encoding="utf-8") as inf:
    new_data = json.load(inf)

# Update stream
ceramic.update_stream(
    ceramic_did_str,
    ceramic_did_seed,
    stream_id,
    new_data,
)

print("Done")
