#!/usr/bin/env bash

# Go into the relevant venv
#cd /home/david/Valory/repos/IEKit && pipenv shell

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