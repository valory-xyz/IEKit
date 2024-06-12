import requests
import os
from payloads import (build_commit_payload, build_data_from_commits,
                              build_genesis_payload)

HTTP_OK = 200

class Ceramic:
    """Ceramic client"""
    # HTTP API docs:
    # https://developers.ceramic.network/build/http/api/#ceramic-http-api

    # Protocol specification:
    # https://github.com/ceramicnetwork/ceramic/blob/main/SPECIFICATION.md

    CLAY_URL_BASE = "https://ceramic-clay.3boxlabs.com"     # read & write, testing
    LOCAL_URL_BASE = "https://locahost:7007"
    GATEWAY_URL_BASE = "https://gateway-clay.ceramic.network"  # gateway node (read only)
    DEFAULT_URL_BASE = "https://ceramic-valory.hirenodes.io"

    def __init__(self, url_base=None) -> None:
        if not url_base:
            url_base = os.getenv("CERAMIC_NODE", None)
            if not url_base:
                url_base = self.DEFAULT_URL_BASE
                print(f"CERAMIC_NODE was not set. Using default value: {self.DEFAULT_URL_BASE}")
        self.url_base = url_base

    def _make_request(self, url: str, request_type: str="get", json_data: dict={}):
        """Handle requests"""
        response = None
        if request_type not in ("get", "post", "delete"):
            raise ValueError(f"Request method '{request_type}' not supported")
        if request_type == "get":
            response = requests.get(url)
        if request_type == "post":
            response = requests.post(url, json=json_data)
        if request_type == "delete":
            response = requests.delete(url)
        if not response:
            return None, None
        headers = response.headers.get("content-type")
        data = response.json() if headers and "application/json" in headers else {}
        return response.status_code, data

    def _request_create_stream(self, genesis_payload: dict):
        return self._make_request(f"{self.url_base}/api/v0/streams", "post", json_data=genesis_payload)

    def _request_create_commit(self, commit_payload: dict):
        return self._make_request(f"{self.url_base}/api/v0/commits", "post", json_data=commit_payload)

    def get_stream(self, streamid: str):
        return self._make_request(f"{self.url_base}/api/v0/streams/{streamid}", "get")

    def pin_stream(self, streamid: str):
        return self._make_request(f"{self.url_base}/api/v0/pins/{streamid}", "post")

    def unpin_stream(self, streamid: str):
        return self._make_request(f"{self.url_base}/api/v0/pins/{streamid}", "delete")

    def get_commits(self, streamid: str):
        return self._make_request(f"{self.url_base}/api/v0/commits/{streamid}", "get")

    def get_data(self, stream_id: str) -> tuple:
        code, data = self.get_commits(stream_id)

        if code != HTTP_OK or not data:
            print(f"Error {code} fetching data from stream {stream_id}")
            return None, None, None

        # Extract first and last commit info
        genesis_cid_str = data["commits"][0]["cid"]
        previous_cid_str = data["commits"][-1]["cid"]

        # Rebuild the current data
        return build_data_from_commits(data["commits"]), genesis_cid_str, previous_cid_str

    def create_stream(self, did: str, did_seed: str, data: dict, extra_metadata: dict = {}) -> str:
        # Prepare the genesis payload
        genesis_payload = build_genesis_payload(did, did_seed, data, extra_metadata)

        # Create a new stream
        code, data = self._request_create_stream(genesis_payload=genesis_payload)
        if code != HTTP_OK or not data:
            print(f"Error creating stream: {data}")
        return data['streamId']

    def update_stream(self, did: str, did_seed: str, stream_id: str, new_data: dict) -> None:
        # Get all the commits
        data, genesis_cid_str, previous_cid_str = self.get_data(stream_id)
        if not data:
            print(f"Error updating stream {stream_id}")
            return

        # Prepare the commit payload
        commit_payload = build_commit_payload(
            did,
            did_seed,
            stream_id,
            data,
            new_data,
            genesis_cid_str,
            previous_cid_str
        )

        # Create a new commit
        code, data =  self._request_create_commit(commit_payload=commit_payload)
        if code != HTTP_OK or not data:
            print(f"Error while updating stream {stream_id}")



