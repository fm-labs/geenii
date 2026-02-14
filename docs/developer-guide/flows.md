# Flows

## Components of a Flow

The building blocks of a flow are its components.

Components define the types of actions, inputs, and outputs that can be used within a flow.

### Inputs

**Types of Inputs:**

- **Text Input**: Accepts string data.
- **Number Input**: Accepts numerical data.
- **Boolean Input**: Accepts true/false values.
- **File Input**: Accepts file uploads.
- **Date Input**: Accepts date values.
- **List Input**: Accepts a list of items.
- **JSON Input**: Accepts structured JSON data.

Anatomy of a component definition:

```json
{
  "component_id": "inputs.text",
  "label": "Text Input",
  "type": "input",
  "inputs": {},
  "configuration": {
    "input_type": {
      "type": "string",
      "enum": [
        "string",
        "number",
        "boolean",
        "file",
        "date",
        "list",
        "json"
      ],
      "default": "string",
      "description": "Type of input to accept."
    },
    "max_length": {
      "type": "integer",
      "default": 255,
      "description": "Maximum length of the input (applicable for string type)."
    },
    "multiline": {
      "type": "boolean",
      "default": false,
      "description": "Whether to allow multiline input (applicable for string type)."
    }
  },
  "outputs": {
    "text": {
      "type": "string",
      "description": "The text input provided by the user."
    }
  }
}
```

## Nodes

Nodes are instances of components within a flow that perform specific functions.

Each node has its own configuration, inputs, and outputs.

Anatomy of a Node:

```json
{
  "nodes": {
    "node_id_1": {
      "type": "input",
      "component": "inputs.text",
      "label": "Text Input",
      "configuration": {
        "input_type": "string",
        "max_length": 500,
        "multiline": false
      },
      "outputs": {
        "text": ""
      },
      "metadata": {
        "position": {
          "x": 100,
          "y": 150
        }
      },
      "state": {
        "last_executed": null,
        "status": "idle"
      }
    },
    "node_id_2": {
      "type": "processing",
      "component": "actions.text_transform",
      "label": "Text Transformer",
      "inputs": {
        "text": ""
      },
      "configuration": {
        "strip_whitespace": true,
        "to_lowercase": true,
        "to_uppercase": false,
        "remove_punctuation": false
      },
      "outputs": {
        "text": 0
      }
    },
    "node_id_3": {
      "type": "output",
      "component": "outputs.display",
      "label": "Display Output",
      "inputs": {
        "input_key": "input_value"
      },
      "configuration": {
        "use_color": false,
        "disable_formatting": true
      },
      "outputs": {}
    }
  },
  "edges": [
    {
      "from_node": "node_id_1",
      "from_output": "text",
      "to_node": "node_id_2",
      "to_input": "text"
    },
    {
      "from_node": "node_id_2",
      "from_output": "text",
      "to_node": "node_id_3",
      "to_input": "input_key"
    }
  ]
}
```