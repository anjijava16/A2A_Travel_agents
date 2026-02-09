https://huggingface.co/blog/1bo/a2a-protocol-explained

# Basic authentic 

```

(a2a-travel-agents) welcome@jaisairams-Laptop basic_agent % python basic_client.py
INFO:__main__:Attempting to fetch public agent card from: http://localhost:9979/.well-known/agent.json
INFO:httpx:HTTP Request: GET http://localhost:9979/.well-known/agent-card.json "HTTP/1.1 200 OK"
INFO:a2a.client.card_resolver:Successfully fetched agent card data from http://localhost:9979/.well-known/agent-card.json: {'capabilities': {'streaming': True}, 'defaultInputModes': ['text'], 'defaultOutputModes': ['text'], 'description': 'Just a hello world agent', 'name': 'Hello World Agent', 'preferredTransport': 'JSONRPC', 'protocolVersion': '0.3.0', 'skills': [{'description': 'just returns hello world', 'examples': ['hi', 'hello world'], 'id': 'hello_world', 'name': 'Returns hello world', 'tags': ['hello world']}], 'supportsAuthenticatedExtendedCard': True, 'url': 'http://0.0.0.0:9999/', 'version': '1.0.0'}
INFO:__main__:Successfully fetched public agent card:
INFO:__main__:{
  "capabilities": {
    "streaming": true
  },
  "defaultInputModes": [
    "text"
  ],
  "defaultOutputModes": [
    "text"
  ],
  "description": "Just a hello world agent",
  "name": "Hello World Agent",
  "preferredTransport": "JSONRPC",
  "protocolVersion": "0.3.0",
  "skills": [
    {
      "description": "just returns hello world",
      "examples": [
        "hi",
        "hello world"
      ],
      "id": "hello_world",
      "name": "Returns hello world",
      "tags": [
        "hello world"
      ]
    }
  ],
  "supportsAuthenticatedExtendedCard": true,
  "url": "http://0.0.0.0:9999/",
  "version": "1.0.0"
}
INFO:__main__:
Using PUBLIC agent card for client initialization (default).
INFO:__main__:
Public card supports authenticated extended card. Attempting to fetch from: http://localhost:9979/agent/authenticatedExtendedCard
INFO:httpx:HTTP Request: GET http://localhost:9979/agent/authenticatedExtendedCard "HTTP/1.1 200 OK"
INFO:a2a.client.card_resolver:Successfully fetched agent card data from http://localhost:9979/agent/authenticatedExtendedCard: {'capabilities': {'streaming': True}, 'defaultInputModes': ['text'], 'defaultOutputModes': ['text'], 'description': 'The full-featured hello world agent for authenticated users.', 'name': 'Hello World Agent - Extended Edition', 'preferredTransport': 'JSONRPC', 'protocolVersion': '0.3.0', 'skills': [{'description': 'just returns hello world', 'examples': ['hi', 'hello world'], 'id': 'hello_world', 'name': 'Returns hello world', 'tags': ['hello world']}, {'description': 'A more enthusiastic greeting, only for authenticated users.', 'examples': ['super hi', 'give me a super hello'], 'id': 'super_hello_world', 'name': 'Returns a SUPER Hello World', 'tags': ['hello world', 'super', 'extended']}], 'supportsAuthenticatedExtendedCard': True, 'url': 'http://0.0.0.0:9999/', 'version': '1.0.1'}
INFO:__main__:Successfully fetched authenticated extended agent card:
INFO:__main__:{
  "capabilities": {
    "streaming": true
  },
  "defaultInputModes": [
    "text"
  ],
  "defaultOutputModes": [
    "text"
  ],
  "description": "The full-featured hello world agent for authenticated users.",
  "name": "Hello World Agent - Extended Edition",
  "preferredTransport": "JSONRPC",
  "protocolVersion": "0.3.0",
  "skills": [
    {
      "description": "just returns hello world",
      "examples": [
        "hi",
        "hello world"
      ],
      "id": "hello_world",
      "name": "Returns hello world",
      "tags": [
        "hello world"
      ]
    },
    {
      "description": "A more enthusiastic greeting, only for authenticated users.",
      "examples": [
        "super hi",
        "give me a super hello"
      ],
      "id": "super_hello_world",
      "name": "Returns a SUPER Hello World",
      "tags": [
        "hello world",
        "super",
        "extended"
      ]
    }
  ],
  "supportsAuthenticatedExtendedCard": true,
  "url": "http://0.0.0.0:9999/",
  "version": "1.0.1"
}
INFO:__main__:
Using AUTHENTICATED EXTENDED agent card for client initialization.
/Users/welcome/Library/Mobile Documents/com~apple~CloudDocs/Tech_Learn/Tech_Repos/python_envs/A2A/A2A_git_commit/A2A_Travel_agents/agents/basic_agent/basic_client.py:102: DeprecationWarning: A2AClient is deprecated and will be removed in a future version. Use ClientFactory to create a client with a JSON-RPC transport.
  client = A2AClient(
INFO:__main__:A2AClient initialized.
INFO:httpx:HTTP Request: POST http://0.0.0.0:9999/ "HTTP/1.1 200 OK"
{'id': 'b691fcc9-95d7-4f18-87e4-fd64e50befc8', 'jsonrpc': '2.0', 'result': {'kind': 'message', 'messageId': 'b5e83d9e-e7b5-4aa3-b54a-bea8c56e2530', 'parts': [{'kind': 'text', 'text': 'Hello World'}], 'role': 'agent'}}
INFO:httpx:HTTP Request: POST http://0.0.0.0:9999/ "HTTP/1.1 200 OK"
{'id': '10903095-9e0b-41d2-9270-37ea234a33f7', 'jsonrpc': '2.0', 'result': {'kind': 'message', 'messageId': '429e9d16-eb0a-4364-ab39-42f86ddb410b', 'parts': [{'kind': 'text', 'text': 'Hello World'}], 'role': 'agent'}}
(a2a-travel-agents) welcome@jaisairams-Laptop basic_agent % 


-- http://localhost:9979/agent/authenticatedExtendedCard
{
"capabilities": {
"streaming": true
},
"defaultInputModes": [
"text"
],
"defaultOutputModes": [
"text"
],
"description": "The full-featured hello world agent for authenticated users.",
"name": "Hello World Agent - Extended Edition",
"preferredTransport": "JSONRPC",
"protocolVersion": "0.3.0",
"skills": [
{
"description": "just returns hello world",
"examples": [
"hi",
"hello world"
],
"id": "hello_world",
"name": "Returns hello world",
"tags": [
"hello world"
]
},
{
"description": "A more enthusiastic greeting, only for authenticated users.",
"examples": [
"super hi",
"give me a super hello"
],
"id": "super_hello_world",
"name": "Returns a SUPER Hello World",
"tags": [
"hello world",
"super",
"extended"
]
}
],
"supportsAuthenticatedExtendedCard": true,
"url": "http://0.0.0.0:9999/",
"version": "1.0.1"
}


-- http://localhost:9979/.well-known/agent-card.json

{
"capabilities": {
"streaming": true
},
"defaultInputModes": [
"text"
],
"defaultOutputModes": [
"text"
],
"description": "Just a hello world agent",
"name": "Hello World Agent",
"preferredTransport": "JSONRPC",
"protocolVersion": "0.3.0",
"skills": [
{
"description": "just returns hello world",
"examples": [
"hi",
"hello world"
],
"id": "hello_world",
"name": "Returns hello world",
"tags": [
"hello world"
]
}
],
"supportsAuthenticatedExtendedCard": true,
"url": "http://0.0.0.0:9999/",
"version": "1.0.0"
}
```