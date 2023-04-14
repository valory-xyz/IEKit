# Release History - `IEKit`

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