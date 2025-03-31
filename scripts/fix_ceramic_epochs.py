import json


with open("contribute_db.json", "r", encoding="utf-8") as db_file:
    data = json.load(db_file)


for user_id, user_data in data["users"].items():
    for tweet_id, tweet in user_data["tweets"].items():
        if tweet["epoch"] and tweet["epoch"] > 38:
            print(f"Tweet {tweet_id} from user {user_data['twitter_handle']}: {tweet['epoch']} -> {38}")
            tweet["epoch"] = 38


with open("contribute_db.json", "w", encoding="utf-8") as db_file:
    json.dump(data, db_file, indent=4)
