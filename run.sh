#!/usr/bin/env bash

TYPE=$1

if [ -z "$TYPE" ]
then
      TYPE="agent"
fi

# Run agent
if [ "$TYPE" = "agent" ]
then
    rm -r impact_evaluator
    find . -empty -type d -delete  # remove empty directories to avoid wrong hashes
    autonomy packages lock
    autonomy fetch --local --agent valory/impact_evaluator && cd impact_evaluator
    cp $PWD/../ethereum_private_key.txt .
    autonomy add-key ethereum ethereum_private_key.txt
    autonomy issue-certificates
    aea -s run
    exit 0
fi

N_AGENTS=$2
DEV_MODE=$3

if [ -z "$N_AGENTS" ]
then
    N_AGENTS=1
fi

if [ -z "$DEV_MODE" ]
then
    DEV_MODE=false
fi

# Run service
if [ "$TYPE" = "service" ]
then
    # Set env vars
    export $(grep -v '^#' .env | xargs)

    # Push packages and fetch service
    make clean

    autonomy push-all

    autonomy fetch --local --service valory/impact_evaluator && cd impact_evaluator

    # Build the image
    autonomy build-image

    # Copy the keys and build the deployment
    cp $KEY_DIR/keys.json .
    autonomy deploy build -ltm

    # Run the deployment
    autonomy deploy run --build-dir abci_build/
    exit 0
fi

echo "Unrecognized type"
exit -1
