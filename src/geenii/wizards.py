from typing import List

from geenii.ai import generate_chat_completion
from geenii.datamodels import ModelMessage, ToolCallResultContent
from geenii.g import execute_tool_call, init_tool_registry
from geenii.config import DEFAULT_COMPLETION_MODEL
from geenii.tools import ToolRegistry


DEFAULT_WIZARD_SYSTEM_PROMPT = """
You are an AI assistant that MUST use available tools when they are relevant.

CORE RULES:

1. NEVER answer from internal knowledge if a tool exists that can provide up-to-date, factual, or external information.
2. ALWAYS evaluate whether a tool should be used BEFORE generating a final response.
3. If a suitable tool exists, you MUST call the tool instead of answering directly.
4. Only produce a final natural-language answer AFTER tool results are returned.
5. Follow the tool calling format EXACTLY.

DECISION PROCESS:

Step 1 — Analyze user intent.
Step 2 — Check available tools.
Step 3 — If any tool can help, return a tool call with the appropriate arguments.
Step 4 — If no tools are relevant, answer the user's question directly.
"""


class Wizard:
    def __init__(self, name, model: str = None, system: str = None, description: str = None,
                 tools: list[str] = None, tool_registry: ToolRegistry = None, mcp_servers: dict[str, str] = None):
        self.name = name
        self.description = description
        self.model = model or DEFAULT_COMPLETION_MODEL
        self.system = system or DEFAULT_WIZARD_SYSTEM_PROMPT
        self.tools = tools or []
        self.mcp_servers = {}

        self._tool_registry = tool_registry or None
        self.init_tool_registry(tool_registry)

    def init_tool_registry(self, tool_registry = None):
        if tool_registry:
            self._tool_registry = tool_registry
        else:
            from geenii.g import get_tool_registry
            self._tool_registry = get_tool_registry()

    def prompt(self, input_text=None):
        if not input_text:
            print("No input provided.")
            return

        print(f"You said: {input_text}")
        #print("System Instructions:", self.system)

        allowed_tools = self.tools
        message_history: List[ModelMessage] = []

        continue_chat = True
        i = 0
        total_tool_calls = 0
        while continue_chat:
            i += 1
            print(f"Wizard: Run #{i}")
            print("Using tools:", allowed_tools)
            response = generate_chat_completion(prompt=input_text,
                                                model=self.model,
                                                system=self.system,
                                                messages=message_history,
                                                tools=allowed_tools
                                                #temperature=temperature,
                                                #output_format=output_format
                                                )
            print(response)
            tool_calls = 0
            for msg in response.output:
                message_history.append(msg)
                for content in msg.content:
                    if content.type == "text":
                        print(content.text)
                    elif content.type == "tool_call":
                        try:
                            # execute the tool call and get the result
                            print(f"[$>] Tool call: {content.name} with args {content.arguments}")
                            tool_call_id = content.call_id
                            tool_result = execute_tool_call(self._tool_registry, content.name, **content.arguments)
                            print(f"Tool result: {len(tool_result)}")
                            # add the tool result to the message history as a new assistant message
                            tool_result_content = tool_result.content[0].text if isinstance(tool_result, list) and len(tool_result) > 0 and tool_result[0].get("content") else str(tool_result)
                            message_history.append(ModelMessage(role="tool", content=[ToolCallResultContent(
                                call_id=tool_call_id,
                                result=tool_result_content)]))

                            tool_calls += 1

                            # remove the tool from the list of available tools for the next iteration to prevent infinite loops
                            if content.name in allowed_tools:
                                allowed_tools.remove(content.name)

                        except Exception as e:
                            print(f"Error executing tool {content.name}: {str(e)}")
                            message_history.append(ModelMessage(role="tool", content=[ToolCallResultContent(
                                result={"error": str(e)})]))

            total_tool_calls += tool_calls
            # end the chat if no tools were called or after 3 iterations to prevent infinite loops
            if tool_calls == 0 or i >= 3:
                continue_chat = False

        print(f"Wizard Chat ended. Total iterations: {i}, total tool calls: {total_tool_calls}")



def load_wizard_from_json(file_path: str) -> Wizard:
    """
    Load a wizard configuration from a JSON file and create a Wizard instance.
    The JSON file should contain the following fields:
    - name: The name of the wizard
    - model: (optional) The AI model to use for this wizard
    - system: (optional) The system prompt to use for this wizard
    - description: (optional) A description of the wizard's purpose and capabilities
    - tools: (optional) A list of tool definitions that the wizard can use
    - mcp_servers: (optional) A dictionary of MCP server configurations that the wizard can connect to
    """
    import json

    with open(file_path, 'r') as f:
        config = json.load(f)

    name = config.get("name")
    model = config.get("model")
    system = config.get("system")
    description = config.get("description")
    tools = config.get("tools", [])
    mcp_servers = config.get("mcp_servers", {})

    if not name:
        raise ValueError("Wizard configuration must include a 'name' field.")

    wizard = Wizard(name=name, model=model, system=system, description=description, tools=tools, mcp_servers=mcp_servers)
    return wizard

def load_wizards_from_directory(directory_path: str) -> List[Wizard]:
    """
    Load all wizard configurations from JSON files in the specified directory and create a list of Wizard instances.
    """
    import os

    wizards = []
    for filename in os.listdir(directory_path):
        if filename.endswith(".wizard.json"):
            file_path = os.path.join(directory_path, filename)
            try:
                wizard = load_wizard_from_json(file_path)
                wizards.append(wizard)
                print(f"Loaded wizard: {wizard.name}")
            except Exception as e:
                print(f"Error loading wizard from {file_path}: {e}")

    return wizards