# IEKit
An toolkit for autonomous services implementing a decentralized Impact Evaluator built with the [Open Autonomy](https://docs.autonolas.network/open-autonomy/) framework.

The demo service for the IEKit tracks mentions of [@autonolas](https://twitter.com/autonolas) on Twitter, assigns scores to them and writes those scores to a [Ceramic](https://ceramic.network/) stream.

## Running a demo service

To learn how to run a demo service based on the IEKit, read the [IEKit technical docs](https://docs.autonolas.network/product/iekit/).

## For Developers

Prepare the environment to build your own IEKit-based service.

- Clone the repository:

      git clone git@github.com:valory-xyz/iekit.git

- System requirements:

    - Python `>=3.7`
    - [Tendermint](https://docs.tendermint.com/v0.34/introduction/install.html) `==0.34.19`
    - [IPFS node](https://docs.ipfs.io/install/command-line/#official-distributions) `==0.6.0`
    - [Pipenv](https://pipenv.pypa.io/en/latest/installation/) `>=2021.x.xx`
    - [Docker Engine](https://docs.docker.com/engine/install/)
    - [Docker Compose](https://docs.docker.com/compose/install/)

- Pull pre-built images:

      docker pull valory/autonolas-registries:latest
      docker pull valory/safe-contract-net:latest

- Create development environment:

      make new_env && pipenv shell

- Configure command line:

      autonomy init --reset --author valory --remote --ipfs --ipfs-node "/dns/registry.autonolas.tech/tcp/443/https"

- Pull packages:

      autonomy packages sync --update-packages
