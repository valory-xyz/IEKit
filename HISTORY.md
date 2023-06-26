# Release History - `IEKit`

## 0.2.8 (2023-06-26)

- Bumps frameworks to `open-autonomy-0.10.7` and `open-aea-1.35.0` #62
- Prepares for minting the service #61
- Fixes olas links #60

## 0.2.7 (2023-06-20)

- Bumps `open-autonomy` framework to `v0.10.6` #58
- Updates Twitter registration requirements #59

## 0.2.6 (2023-06-07)

- Bumps `open-autonomy` framework to `v0.10.5.post2` #57
- Pins typing extension #56

## 0.2.5 (2023-05-31)

- Bumps frameworks to `open-autonomy-0.10.5.post1` and `open-aea-1.34.0` #55
- Bumps to `tomte@v0.2.12` and cleans up the repo #53
- Implements twitter shortened link verification #52

## 0.2.4 (2023-05-09)

- Bumps frameworks to `open-autonomy-0.10.3` and `open-aea-1.33`
- Implements t.co link verification for registrations

## 0.2.3 (2023-04-25)

- Bumps `open-autonomy` framework

# 0.2.2 (2023-04-14)

- Bumps `open-autonomy` and `open-aea` frameworks
- Adds extra overrides to the agent and the service

# 0.2.1.post1 (2023-04-03)

- Bump `open-autonomy` to `v0.10.0.post2`
- Sets the `p2p_libp2p_client` as non abstract to enable `ACN`

# 0.2.1 (2023-03-29)

- Fixes an issue with the Ceramic protocol not being able to process big integers
- Adds the period number to the healthcheck

# 0.2.0 (2023-03-27)

- Bumps to open-autonomy@v0.10.0.post1, open-aea@1.31.0, and tomte@0.2.4
- The skills have been extracted and the FSM reworked
- The service now also reads generic scores from a Ceramic stream (apart from the Twitter scores)
- Implements wallet linking via tweets
- Adds liccheck to the linters
- Updates documentation

# 0.1.0 (2023-03-15)

- First release of IEKit
