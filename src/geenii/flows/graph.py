import abc

import pydantic


class ComponentModel(pydantic.BaseModel):
    pass

class ComponentInputs(ComponentModel):
    pass

class ComponentOutputs(ComponentModel):
    pass

class Component(abc.ABC):
    component_id: str = None
    label: str = None
    inputs: type[ComponentInputs] | None = None
    outputs: type[ComponentInputs] | None = None
    configuration = None

    @staticmethod
    @abc.abstractmethod
    def execute(input_data, config):
        pass


class TextInputComponentOutputs(ComponentOutputs):
    text: str

class TextInputComponentConfiguration(ComponentModel):
    placeholder: str | None = None
    default_value: str | None = None
    max_length: int | None = None
    multiline: bool = False


class TextInputComponent(Component):
    component_id = "inputs.text"
    label = "Text Input"
    inputs = None
    outputs = TextInputComponentOutputs
    configuration = TextInputComponentConfiguration

    @staticmethod
    def execute(input_data, config):
        pass


class TextTransformComponentInputs(ComponentInputs):
    text: str

class TextTransformComponentOutputs(ComponentOutputs):
    transformed_text: str

class TextTransformComponentConfiguration(ComponentModel):
    operation: str  # e.g., "uppercase", "lowercase", "reverse"

class TextTransformComponent(Component):
    component_id = "transform.text"
    label = "Text Transform"
    inputs = TextTransformComponentInputs
    outputs = TextTransformComponentOutputs
    configuration = TextTransformComponentConfiguration

    @staticmethod
    def execute(input_data, config):
        text = input_data.text
        operation = config.operation.lower()
        if operation == "uppercase":
            transformed_text = text.upper()
        elif operation == "lowercase":
            transformed_text = text.lower()
        elif operation == "reverse":
            transformed_text = text[::-1]
        else:
            transformed_text = text  # No operation
        return TextTransformComponentOutputs(transformed_text=transformed_text)


class Node:
    def __init__(self, node_id, node_type, component, label, configuration):
        self.node_id = node_id
        self.node_type = node_type
        self.component = component  # instance of Component
        self.label = label
        self.configuration = configuration  # dict of configuration settings
        self.inputs = {}  # dict to hold input values
        self.outputs = {}  # dict to hold output values

    def execute(self):
        # Placeholder for node execution logic
        pass


class Edge:
    def __init__(self, from_node, from_output, to_node, to_input):
        self.from_node = from_node
        self.from_output = from_output
        self.to_node = to_node
        self.to_input = to_input


class FlowGraph:

    def __init__(self):
        self.nodes = {}
        self.edges = []

    def add_node(self, node_id, node_type, component, label, configuration):
        self.nodes[node_id] = {
            "type": node_type,
            "component": component,
            "label": label,
            "configuration": configuration,
            "inputs": {},
            "outputs": {}
        }

    def add_edge(self, from_node, from_output, to_node, to_input):
        self.edges.append({
            "from_node": from_node,
            "from_output": from_output,
            "to_node": to_node,
            "to_input": to_input
        })

    def execute(self):
        # Placeholder for flow execution logic
        pass

