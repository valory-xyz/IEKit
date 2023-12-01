![IEKit](images/iekit.svg){ align=left }
The Impact Evaluator Kit (IEKit) is an enhanced version of the [CoordinationKit](https://docs.autonolas.network/product/coordinationkit/), which leverages [Ceramic streams](https://developers.ceramic.network/docs/advanced/standards/stream-programs/) to automate the tracking and rewarding of users' contributions on the ecosystem. We provide a demo agent service based on the IEKit which is designed to track contributions in the form of Twitter mentions of the Autonolas DAO ([@autonolas](https://twitter.com/autonolas)). Generic scores can be also read from a [Ceramic stream](https://developers.ceramic.network/docs/advanced/standards/stream-programs/). The demo service implements three main features:

1. **Monitor for new users' registrations.** Reads registered users both from tweets that contain the `#olas` hashtag and also from a [Ceramic stream](https://developers.ceramic.network/docs/advanced/standards/stream-programs/) that contains user data like discord ids and wallet addresses.

2. **Monitor for users' contributions.** The service periodically scans for new mentions of @autonolas on Twitter and updates to the scores stream, and increments and updates the score of the corresponding user.

3. **Update the badge of users according to their score.** To access the badge image associated to a user's NFT, the metadata URI associated to it is redirected to an agent in the service. Upon reading the concrete NFT from the request, the service provides the IPFS address of the image, which is updated periodically in relation to the user's score.

The demo service uses dedicated [Ceramic streams](https://developers.ceramic.network/docs/advanced/standards/stream-programs/) as a persistent solution to store users' scores and registration metadata.
The service demonstrates the applicability of the IEKit to build a particular use case, but of course, the IEKit is modular by design and can be adapted to a range of custom impact evaluators.

## Demo

!!! warning "Important"

    This section is under active development - please report issues in the [Autonolas Discord](https://discord.com/invite/z2PT65jKqQ).

In order to run a local demo service based on the IEKit:

1. [Set up your system](https://docs.autonolas.network/open-autonomy/guides/set_up/) to work with the Open Autonomy framework. We recommend that you use these commands:

    ```bash
    mkdir your_workspace && cd your_workspace
    touch Pipfile && pipenv --python 3.10 && pipenv shell

    pipenv install open-autonomy[all]==0.13.6
    autonomy init --remote --ipfs --reset --author=your_name
    ```

2. Fetch the IEKit.

    ```bash
    autonomy fetch valory/impact_evaluator:0.1.0:bafybeie4wxdcf6z7mjmvxbttvvclynkzj23vsxgoau4gj3wayzb2ufwumi --service
    ```

3. Build the Docker image of the service agents

    ```bash
    cd impact_evaluator
    autonomy build-image
    ```

4. Prepare the `keys.json` file containing the wallet address and the private key for each of the agents.

    ??? example "Example of a `keys.json` file"

        <span style="color:red">**WARNING: Use this file for testing purposes only. Never use the keys or addresses provided in this example in a production environment or for personal use.**</span>

        ```json
        [
          {
              "address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
              "private_key": "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a"
          },
          {
              "address": "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc",
              "private_key": "0x8b3a350cf5c34c9194ca85829a2df0ec3153be0318b5e2d3348e872092edffba"
          },
          {
              "address": "0x976EA74026E726554dB657fA54763abd0C3a0aa9",
              "private_key": "0x92db14e403b83dfe3df233f83dfa3a0d7096f21ca9b0d6d6b8d88b2b4ec1564e"
          },
          {
              "address": "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955",
              "private_key": "0x4bbbf85ce3377467afe5d46f804f221813b2bb87f24d81f60f1fcdbf7cbf4356"
          }
        ]
        ```

5. Prepare the environment and build the service deployment.

    1. Create a [Twitter API Bearer Token](https://developer.twitter.com/en/portal/dashboard).

    2. Create a Ceramic Decentralized Identity (DID) using [Glaze](https://github.com/ceramicstudio/js-glaze).

    3. Using the DID created in the previous step, create two empty Ceramic streams. The service will optionally read generic scores from the first one and will write scores to the second one.

    4. Create an API key for [Infura](https://www.infura.io/) or your preferred provider.

    5. Create an `.env` file with the required environment variables, modifying its values to your needs.

        ```bash
        ETHEREUM_LEDGER_RPC=https://goerli.infura.io/v3/<infura_api_key>
        ETHEREUM_LEDGER_CHAIN_ID=1
        DYNAMIC_CONTRIBUTION_CONTRACT_ADDRESS=0x7C3B976434faE9986050B26089649D9f63314BD8
        EARLIEST_BLOCK_TO_MONITOR=16097553
        CERAMIC_DID_SEED=<ceramic_seed_did>
        CERAMIC_DID_STR=<ceramic_did_string>
        CERAMIC_API_BASE=<ceramic_node_endpoint>
        CENTAURS_STREAM_ID=<centaurs_stream_id>
        CERAMIC_DB_STREAM_ID=<main_db_stream_id>
        MANUAL_POINTS_STREAM_ID=<generic_scores_stream_id>
        CENTAUR_ID_TO_SECRETS='{"your_centaur_id":{"orbis":{"context":"orbis_context_stream_id","did_seed":"your_did_seed","did_str":"your_did_str"},"twitter":{"consumer_key":"your_consumer_key","consumer_secret":"your_consumer_secret","access_token":"your_access_token","access_secret":"your_access_secret"}}}'
        OPENAI_API_KEY_0=<openai_api_key>
        OPENAI_API_KEY_1=<openai_api_key>
        OPENAI_API_KEY_2=<openai_api_key>
        OPENAI_API_KEY_3=<openai_api_key>
        TWITTER_API_BEARER_TOKEN=<twitter_api_token>
        RESET_PAUSE_DURATION=30
        ALL_PARTICIPANTS='["0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65","0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc","0x976EA74026E726554dB657fA54763abd0C3a0aa9","0x14dC79964da2C08b23698B3D3cc7Ca32193d9955"]'
        POINTS_TO_IMAGE_HASHES='{"0":"bafybeiabtdl53v2a3irrgrg7eujzffjallpymli763wvhv6gceurfmcemm","100":"bafybeid46w6yzbehir7ackcnsyuasdkun5aq7jnckt4sknvmiewpph776q","50000":"bafybeigbxlwzljbxnlwteupmt6c6k7k2m4bbhunvxxa53dc7niuedilnr4","100000":"bafybeiawxpq4mqckbau3mjwzd3ic2o7ywlhp6zqo7jnaft26zeqm3xsjjy","150000":"bafybeie6k53dupf7rf6622rzfxu3dmlv36hytqrmzs5yrilxwcrlhrml2m"}'
        USE_ACN=false
        ```

        and export them:

        ```bash
        export $(grep -v '^#' .env | xargs)
        ```

    6. Build the service deployment.

        ```bash
        autonomy deploy build keys.json -ltm
        ```

6. Run the service.

    ```bash
    cd abci_build
    autonomy deploy run
    ```

    You can cancel the local execution at any time by pressing ++ctrl+c++.

7. Check that the service is running. Open a separate terminal and execute the command below. You should see the service transitioning along different states.

    ```bash
    docker logs -f impactevaluator_abci_0 | grep -E 'Entered|round is done'
    ```

8. You can try some examples on how to curl the service endpoints from inside one of the agent containers. For example:

    ```bash
    # Get the metadata for the token with id=1
    curl localhost:8000/1 | jq

    # Output
    {
      "title": "Autonolas Contribute Badges",
      "name": "Badge 1",
      "description": "This NFT recognizes the contributions made by the holder to the Autonolas Community.",
      "image": "ipfs://bafybeiabtdl53v2a3irrgrg7eujzffjallpymli763wvhv6gceurfmcemm",
      "attributes": []
    }

    # Get the service health status
    curl localhost:8000/healthcheck | jq

    # Output
    {
      "seconds_since_last_reset": 15.812911033630371,
      "healthy": true,
      "seconds_until_next_update": -5.812911033630371
    }
    ```

## Build

1. Fork the [IEKit repository](https://github.com/valory-xyz/iekit).
2. Make the necessary adjustments to tailor the service to your needs. This could include:
    * Adjust configuration parameters (e.g., in the `service.yaml` file).
    * Expand the service finite-state machine with your custom states.
3. Run your service as detailed above.

!!! tip "Looking for help building your own?"

    Refer to the [Autonolas Discord community](https://discord.com/invite/z2PT65jKqQ), or consider ecosystem services like [Valory Propel](https://propel.valory.xyz) for the fastest way to get your first autonomous service in production.
