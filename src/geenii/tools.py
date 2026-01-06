import abc
from typing import List

import pydantic

class Tool(abc.ABC):

    def __init__(self, name: str, description: str = "", parameters: dict = None):
        self.type = "function"
        self.name = name
        self.description = description
        self.parameters = parameters or {}

    @abc.abstractmethod
    def invoke(self, **kwargs):
        raise NotImplementedError("This method should be overridden by subclasses.")

    def to_tool_def(self) -> dict:
        """
        Convert the tool to a tool definition dictionary.
        """
        return {
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

    # def to_openai(self) -> dict:
    #     """
    #     Convert the tool to an OpenAI function definition format.
    #     """
    #     if self.type != "function":
    #         raise ValueError("Only 'function' type tools can be converted to OpenAI format.")
    #
    #     return {
    #         "type": "function",
    #         "name": self.name,
    #         "description": self.description,
    #         "parameters": self.parameters
    #     }
    #
    # def to_ollama(self) -> dict:
    #     """
    #     Convert the tool to an Ollama tool definition format.
    #     """
    #     if self.type != "function":
    #         raise ValueError("Only 'function' type tools can be converted to Ollama format.")
    #
    #     return {
    #         "type": "function",
    #         "function": {
    #             "name": self.name,
    #             "description": self.description,
    #             "parameters": self.parameters
    #         }
    #     }


class PythonTool(Tool):
    def __init__(self, name: str, description: str = "", parameters: dict = None, handler=None):
        super().__init__(name, description, parameters)
        self.handler = handler  # Function to handle the tool's operation

    def invoke(self, **kwargs):
        if self.handler:
            return self.handler(**kwargs)
        raise NotImplementedError("Tool handler is not implemented.")


class McpTool(Tool):
    def __init__(self, name: str, mcp_server_id: str, description: str = "", parameters: dict = None):
        super().__init__(name, description, parameters)
        self.type = "function"
        self.mcp_server_id = mcp_server_id  # MCP server ID where the tool is hosted

    def invoke(self, **kwargs):
        # get_mcp_client_for_server and call the tool via MCP client
        # call_mcp_tool(self.mcp_server_id, self.name, kwargs)
        raise NotImplementedError("MCP tool invocation should be handled via MCP client.")


class McpServerConfig(pydantic.BaseModel):
    pass


class ToolDef(pydantic.BaseModel):
    """
    Represents a tool that can be used by the AI assistant.
    """
    type: str # "function"
    name: str
    description: str | None = None
    parameters: dict = dict()
    mcp_server_id: str | None = None  # Optional MCP server ID if the tool is hosted on an MCP server

    def to_openai(self) -> dict:
        """
        Convert the tool to an OpenAI function definition format.
        """
        if self.type != "function":
            raise ValueError("Only 'function' type tools can be converted to OpenAI format.")

        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

    def to_ollama(self) -> dict:
        """
        Convert the tool to an Ollama tool definition format.
        """
        if self.type != "function":
            raise ValueError("Only 'function' type tools can be converted to Ollama format.")

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


tool_registry: List[ToolDef] = list()


def register_tool_def(tool_definition: dict) -> None:
    """
    Register a new tool definition.

    :param tool_definition: Definition of the tool, typically a dictionary.
    """
    if not isinstance(tool_definition, dict):
        raise TypeError("Tool definition must be a dictionary.")
    if "name" not in tool_definition:
        raise ValueError("Tool definition must contain a 'name' key.")

    tool_name = tool_definition["name"]
    if get_tool_def_by_name(tool_name) is not None:
        raise ValueError(f"Tool with ID '{tool_name}' is already registered.")

    tool = ToolDef(
        type=tool_definition.get("type", "function"),
        name=tool_name,
        description=tool_definition.get("description", None),
        parameters=tool_definition.get("parameters", {})
    )
    tool_registry.append(tool)
    print(f"Registered tool: {tool_name}")


def get_tool_def_by_name(tool_name) -> ToolDef | None:
    """
    Retrieve a tool by its unique identifier.

    :param tool_name: Unique identifier for the tool.
    :return: Tool definition if found, None otherwise.
    """
    return next((t for t in tool_registry if t.name == tool_name), None)


def resolve_tool_defs(tool_names: List[str]) -> List[dict]:
    """
    Resolve tool IDs to their full definitions.

    :param tool_names: List of tool names.
    :return: List of resolved tools.
    """
    resolved_tools = []
    for tool_name in tool_names:
        resolved_tool = get_tool_def_by_name(tool_name)
        if resolved_tool:
            resolved_tools.append(resolved_tool.model_dump())
    return resolved_tools
