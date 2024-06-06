if test -d impact_evaluator; then
  echo "Removing previous agent build"
  rm -r impact_evaluator
fi

find . -empty -type d -delete  # remove empty directories to avoid wrong hashes
autonomy packages lock
autonomy fetch --local --agent valory/impact_evaluator
python scripts/aea-config-replace.py
cd impact_evaluator

cp $PWD/../ethereum_private_key.txt .
autonomy add-key ethereum ethereum_private_key.txt
autonomy issue-certificates
aea -s run