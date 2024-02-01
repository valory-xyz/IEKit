#!/usr/bin/env bash

# Go into the relevant venv
#cd /home/david/Valory/repos/IEKit && pipenv shell

# Set env vars
export $(grep -v '^#' .1env | xargs)

# Push packages and fetch service
make clean

autonomy push-all

autonomy fetch --local --service valory/impact_evaluator_local && cd impact_evaluator_local

# Build the image
autonomy build-image

# Copy the keys and build the deployment
cp $KEY_DIR/keys1_gnosis.json ./keys.json
autonomy deploy build -ltm

# Run the deployment
autonomy deploy run --build-dir abci_build/