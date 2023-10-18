# Twitter Protocol

## Description

This is a protocol for interacting with Twitter.

## Specification

```yaml
---
name: twitter
author: valory
version: 0.1.0
description: A protocol for interacting with Twitter.
license: Apache-2.0
aea_version: '>=1.0.0, <2.0.0'
protocol_specification_id: valory/twitter:0.1.0
speech_acts:
  request:
    data: pt:str
  response:
    tweet_id: pt:str
...
---
initiation: [request]
reply:
  request: [response]
  response: []
termination: [response]
roles: {skill, connection}
end_states: [successful]
keep_terminal_state_dialogues: false
...
```

## Links

