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

"""This package contains helper function to prepare Ceramic payloads."""

import hashlib
import json
from base64 import b64decode, b64encode, urlsafe_b64decode, urlsafe_b64encode

import dag_cbor
import jsonpatch
from authlib.jose import JsonWebSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from multiformats import CID


DAG_CBOR_CODEC_CODE = 113
SHA2_256_CODE = 18


def encode_cid(
    multihash: bytearray, cid_version: int = 1, code: int = DAG_CBOR_CODEC_CODE
) -> bytearray:
    """CID encoding"""
    code_offset = 1
    hash_offset = 2
    _bytes = bytearray([0] * (hash_offset + len(multihash)))
    _bytes.insert(0, cid_version)
    _bytes.insert(code_offset, code)
    _bytes[hash_offset:] = multihash
    return _bytes


def create_digest(digest: bytearray, code: int = SHA2_256_CODE) -> bytearray:
    """Create a digest"""
    size = len(digest)
    size_offset = 1
    digest_offset = 2
    _bytes = bytearray([0] * (digest_offset + size))
    _bytes.insert(0, code)
    _bytes.insert(size_offset, size)
    _bytes[digest_offset:] = digest
    return _bytes


def base64UrlEncode(data):
    """Base64 encoding"""
    return urlsafe_b64encode(data).rstrip(b"=")


def sign_ed25519(payload: dict, did: str, seed: str):
    """Sign a payload using EdDSA (ed25519)"""

    payload_b64decoded = urlsafe_b64decode(payload)

    # Create an ed25519 from the seed
    key_ed25519 = Ed25519PrivateKey.from_private_bytes(bytearray.fromhex(seed))

    # Sign the payload
    jws = JsonWebSignature()
    protected = {"alg": "EdDSA", "kid": did + "#" + did.split(":")[-1]}
    signature = jws.serialize_compact(protected, payload_b64decoded, key_ed25519)
    signature_data = {
        k: v
        for k, v in zip(
            ("protected", "payload", "signature"), signature.decode("utf-8").split(".")
        )
    }

    return json.dumps(signature_data, sort_keys=True)


def build_data_from_commits(commits):
    """Rebuild the current data from the diff patches"""

    # Iterate over the commits and get the data diffs
    patches = []
    for commit in commits:
        # Skip anchor commits
        if "linkedBlock" not in commit["value"].keys():
            continue  # pragma: no cover

        linked_block = commit["value"]["linkedBlock"]

        decoded_block = decode_linked_block(linked_block)
        if "data" in decoded_block:
            patches.append(decoded_block["data"])
        else:
            patches.append({})

    # Apply the patches sequentially
    if not patches:
        return {}

    # If the first patch only contains operations, we start with an empty object.
    # In other case, the first patch is the base content.
    if all(
        type(ops) == dict
        and all(field in ops.keys() for field in ["op", "value", "path"])
        for ops in patches[0]
    ):
        content = {}
    else:
        content = patches.pop(0)

    for patch in patches:
        content = jsonpatch.apply_patch(content, patch)

    return content


def decode_linked_block(linked_block: str) -> dict:
    """Decode the block data"""
    # Base64 decoding will raise binascii.Error: Incorrect padding if there is not enough padding
    # We can add extra b"=="" to avoid this and the decoder will trim out the unneeded ones. See here:
    # https://stackoverflow.com/questions/2941995/python-ignore-incorrect-padding-error-when-base64-decoding
    block_bytes = linked_block.encode("utf-8")
    encoded_bytes = b64decode(block_bytes + b"==")
    return dag_cbor.decode(encoded_bytes)


def encode_and_sign_payload(payload: dict, did: str, did_seed: str) -> dict:
    """Create the JSON Web Signature of a Ceramic update payload"""

    # This code replicates the following JS implementation:
    # https://github.com/ceramicnetwork/js-did/blob/101e27cd306aced9322ec01a920b987006625d51/packages/dids/src/did.ts#L301
    # https://github.com/ceramicnetwork/js-did/blob/101e27cd306aced9322ec01a920b987006625d51/packages/dids/src/did.ts#L265

    # Encode the payload using the DAG_CBOR codec
    encoded_bytes = dag_cbor.encode(data=payload)
    linked_block = b64encode(encoded_bytes).decode("utf-8")

    # SHA256 hash
    hashed = create_digest(bytearray.fromhex(hashlib.sha256(encoded_bytes).hexdigest()))

    # Create the hash CID
    cid = CID(base="base32", version=1, codec=DAG_CBOR_CODEC_CODE, digest=hashed)
    link = str(cid)

    # Create the payload CID
    cid_bytes = encode_cid(hashed)
    payload_cid = base64UrlEncode(cid_bytes)

    # Sign the payload using ed25519
    # https://github.com/ceramicnetwork/key-did-provider-ed25519/blob/60c78dce7df4d7231bc5280dfcb8d9c953d12a20/src/index.ts#L73
    # https://github.com/decentralized-identity/did-jwt/blob/4efd9a755738a8a6347611cbded042a133d0b91a/src/JWT.ts#L272
    signature_data = json.loads(
        sign_ed25519(payload_cid.decode("utf-8"), did, did_seed)
    )

    return linked_block, link, payload_cid.decode("utf-8"), signature_data


def build_commit_payload(
    did: str, did_seed: str, stream_id: str, data: dict, final_data: dict
):
    """Build a commit payload"""

    initial_data = data["data"]
    genesis_cid_str = data["genesis_cid_str"]
    previous_cid_str = data["previous_cid_str"]

    # Create a diff patch from the old data to the new one
    patch = jsonpatch.make_patch(initial_data, final_data)

    # Build the commit data
    commit_data = {
        "header": {},
        "data": patch.patch,
        "id": CID.decode(genesis_cid_str),
        "prev": CID.decode(previous_cid_str),
    }

    # Encode and sign the data
    linked_block, link, payload_cid, signature_data = encode_and_sign_payload(
        commit_data, did, did_seed
    )

    # Build the update payload
    commit_payload = {
        "streamId": stream_id,
        "opts": {
            "anchor": True,
            "publish": True,
            "sync": 0,
            "asDID": {"_client": {}, "_resolver": {"registry": {}}, "_id": did},
        },
        "commit": {
            "jws": {
                "payload": payload_cid,
                "signatures": [
                    {
                        "protected": signature_data["protected"],
                        "signature": signature_data["signature"],
                    }
                ],
                "link": link,
            },
            "linkedBlock": linked_block,
        },
    }

    return commit_payload
