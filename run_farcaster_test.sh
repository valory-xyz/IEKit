rm -r farcaster_test
find . -empty -type d -delete  # remove empty directories to avoid wrong hashes
autonomy packages lock
autonomy fetch --local --agent valory/farcaster_test && cd farcaster_test

# Replace aea-config with the configured one
aeaconfig="/home/david/Cloud/env/contribute/farcaster-aea-config.yaml"
if [ -e "$aeaconfig" ]; then
  cp $aeaconfig ./aea-config.yaml
fi

cp $PWD/../ethereum_private_key.txt .
autonomy add-key ethereum ethereum_private_key.txt
autonomy issue-certificates
aea -s run