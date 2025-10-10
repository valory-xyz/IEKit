# LLM Protocol

## Description

This is a protocol for interacting with LLm.

## Specification

```yaml
---
name: llm
author: valory
version: 1.0.0
description: A protocol for LLM requests and responses.
license: Apache-2.0
aea_version: '>=2.0.0, <3.0.0'
protocol_specification_id: valory/llm:1.0.0
speech_acts:
  request:
    prompt_template: pt:str
    prompt_values: pt:dict[pt:str, pt:str]
  response:
    value: pt:str
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

