from ceramic import Ceramic
import json
import os
import dotenv

dotenv.load_dotenv(override=True)

ceramic = Ceramic(os.getenv("CERAMIC_API_BASE"))

stream_id = os.getenv("CERAMIC_DB_STREAM_ID")

# Get the data
data, _, _ = ceramic.get_data(stream_id)

# Save to json
with open("stream.json", "w", encoding="utf-8") as out_file:
    json.dump(data, out_file, indent=4)

print("Done reading stream {stream_id}")
