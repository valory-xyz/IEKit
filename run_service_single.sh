#!/usr/bin/env bash

REPO_PATH=$PWD

export $(grep -v '^#' .1env | xargs)

# Remove previous service build
if test -d impact_evaluator_local; then
  echo "Removing previous service build"
  sudo rm -r impact_evaluator_local
fi

# Push packages and fetch service
make clean

autonomy push-all

autonomy fetch --local --service valory/impact_evaluator_local && cd impact_evaluator_local

# Build the image
autonomy init --reset --author valory --remote --ipfs --ipfs-node "/dns/registry.autonolas.tech/tcp/443/https"
autonomy build-image

# Copy .env file
cp $REPO_PATH/.env .

# Copy the keys and build the deployment
cp $REPO_PATH/keys1.json ./keys.json
autonomy deploy build -ltm

# Run the deployment
folder_name=$(ls -d abci_build_????/)
autonomy deploy run --build-dir $folder_name