#!/usr/bin/env bash

# Set env vars
export $(grep -v '^#' .sample_env | xargs)

# Push packages and fetch service
make clean

autonomy push-all

autonomy fetch --local --service valory/impact_evaluator_local

# Copy the keys and build the deployment
cp $KEYS_PATH ./impact_evaluator_local/keys.json
cd impact_evaluator_local

# Build the image
autonomy build-image

# Build the deployment
autonomy deploy build -ltm

# Run the deployment
autonomy deploy run --build-dir abci_build/