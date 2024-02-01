rm -r impact_evaluator
find . -empty -type d -delete  # remove empty directories to avoid wrong hashes
autonomy packages lock
autonomy fetch --local --agent valory/impact_evaluator && cd impact_evaluator

# Replace aea-config with the configured one
aeaconfig="/home/david/Cloud/env/contribute/aea-config.yaml"
if [ -e "$aeaconfig" ]; then
  cp $aeaconfig .
fi

cp $PWD/../ethereum_private_key.txt .
autonomy add-key ethereum ethereum_private_key.txt
autonomy issue-certificates
aea -s run