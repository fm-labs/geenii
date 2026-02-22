from typing import List, AsyncGenerator
import json

from geenii.ai import generate_chat_completion
from geenii.chat.chat_bots import BotInterface
from geenii.chat.chat_models import ToolCallResultContent, ContentPart, TextContent
from geenii.datamodels import ModelMessage
from geenii.config import DEFAULT_COMPLETION_MODEL
from geenii.tools import execute_tool_call, ToolRegistry

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


def message_to_prompt(message: str | list[ContentPart]) -> str:
    if isinstance(message, str):
        return message
    elif isinstance(message, list):
        return " ".join([content.to_text() for content in message])
    else:
        raise ValueError("Unsupported message format")


class Wizard(BotInterface):

    def __init__(self, name, model: str = None, system_prompt: str = None, description: str = None,
                 tools: set[str] = None, tool_registry: ToolRegistry = None,
                 mcp_servers: dict[str, str] = None,
                 skills: set[str] = None):

        self.name = name
        self.description = description
        self.model = model or DEFAULT_COMPLETION_MODEL
        self.system_prompt = system_prompt or DEFAULT_WIZARD_SYSTEM_PROMPT
        self.tools = tools or set()
        self.mcp_servers = {}
        self.skills = skills or set()

        self._tool_registry = tool_registry or None
        self._skill_cache = {}

    async def prompt(self, message: str | list[ContentPart]) -> AsyncGenerator[ContentPart, None]:
        if not message:
            print("No input provided.")
            yield TextContent(text=f"How can I assist you today?")

        full_system_prompt = self.build_system_prompt()
        tool_names = self.tools
        message_history: List[ModelMessage] = []
        prompt = message_to_prompt(message)

        continue_chat = True
        i = 0
        total_tool_calls = 0
        while continue_chat:
            i += 1
            print(f"Wizard: Run #{i}")
            print("Using tools:", tool_names)

            # todo - run sync task in thread pool to avoid blocking the event loop while waiting for the response
            #  and yield intermediate content parts as they come in instead of waiting for the full response
            response = generate_chat_completion(prompt=prompt,
                                                model=self.model,
                                                system=full_system_prompt,
                                                messages=message_history,
                                                tools=tool_names,
                                                tool_registry=self._tool_registry,
                                                # temperature=temperature,
                                                # output_format=output_format
                                                )
            print(response)
            tool_calls = 0
            output_parts: List[ContentPart] = []
            for item in response.output:
                if item.type == "text":
                    print(item.text)
                    output_parts.append(TextContent(text=item.text))
                elif item.type == "tool_call":
                    tool_call_id = item.call_id
                    try:
                        # execute the tool call and get the result
                        print(f"[>] Tool call: {item.name} with args {item.arguments}")
                        tool_usage_approved = self.request_tool_execution(tool_name=item.name, arguments=item.arguments,
                                                                          call_id=tool_call_id)
                        if tool_usage_approved:
                            print(f"[>] Tool usage approved: {item.name}")
                            tool_result = execute_tool_call(self._tool_registry, item.name, **item.arguments)
                            tool_calls += 1
                            print(f"Tool result", tool_calls)
                            output_parts.append(ToolCallResultContent(call_id=tool_call_id, result=tool_result))
                        else:
                            print(f"Tool execution for {item.name} was rejected by the request_tool_execution method.")
                            output_parts.append(ToolCallResultContent(call_id=tool_call_id,
                                                                      result={"error": "Tool execution rejected."}))

                        # remove the tool from the list of available tools for the next iteration to prevent infinite loops
                        if item.name in tool_names:
                            tool_names.remove(item.name)

                    except Exception as e:
                        print(f"Error executing tool {item.name}: {str(e)}")
                        # print stack trace
                        import traceback
                        traceback.print_exc()

                        output_parts.append(ToolCallResultContent(call_id=tool_call_id, result={"error": str(e)}))
                        raise e
                else:
                    print(f"Unknown content part type: {item.type}")
                    output_parts.append(TextContent(text=f"[Unknown content type: {item.type}]"))

            output_message = ModelMessage(role="assistant", content=output_parts)
            message_history.append(output_message)

            total_tool_calls += tool_calls
            # end the chat if no tools were called or after 3 iterations to prevent infinite loops
            if tool_calls == 0 or i >= 3:
                continue_chat = False

        print(f"Wizard Chat ended. Total iterations: {i}, total tool calls: {total_tool_calls}")
        yield TextContent(text=f"Wizard Chat ended. Total iterations: {i}, total tool calls: {total_tool_calls}")

    def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        """
        This method can be overridden to implement custom logic for approving or rejecting tool execution requests.
        By default, it approves all tool execution requests.
        """
        return True

    def build_system_prompt(self) -> str:
        """
        Build the full system prompt for the wizard, including the base system prompt and any additional information from loaded skills.
        """
        skills_prompt = self.build_skills_prompt()
        full_system_prompt = self.system_prompt + "\n\n" + skills_prompt
        return full_system_prompt

    def build_skills_prompt(self) -> str:
        """
        Returns a combined prompt for all loaded skills that can be included in the system prompt
        to provide the wizard with information about its skills and how to use them.
        :return:
        """
        skills_prompt = ""
        if len(self._skill_cache) > 0:
            skills_prompt += "## Skills\n\n"
            for skill_name, skill in self._skill_cache.items():
                skills_prompt += f"### {skill_name}\n\n"
                skills_prompt += f"{skill['description']}\n\n"
                skills_prompt += f"Tools: {', '.join(skill['tools'])}\n\n"
                skills_prompt += f"System instructions:\n{skill['system']}\n\n"
        return skills_prompt

    def load_skill(self, skill_name: str):
        """
        Load a skill by name and add its tools to the wizard's available tools.
        This is a placeholder method and should be implemented to load actual skills and their tools.
        """
        print(f"Loading skill: {skill_name}")
        # Example: if skill_name == "file_management", load file management tools
        if skill_name == "geenii/mac-skills":
            tools = ["file_exists", "file_read", "execute_command"]

            skill = {
                "name": skill_name,
                "description": "A set of skills for managing files and executing commands on MacOSX.",
                "tools": tools,
                "system": """
                
                """
            }

            self.tools.update(tools)
            self.skills.add(skill_name)
            self._skill_cache.update({skill_name: skill})
            print(f"Loaded skill '{skill_name}' with tools: {tools}")
        else:
            print(f"Skill '{skill_name}' not found.")


class CliWizard(Wizard):

    def request_tool_execution(self, tool_name: str, arguments: dict, call_id: int) -> bool:
        user_input = input(f"Tool '{tool_name}' wants to execute with arguments {arguments}. Approve? (y/n): ")
        return user_input.lower() == 'y'


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

    wizard = Wizard(name=name, model=model, system_prompt=system, description=description,
                    tools=tools, mcp_servers=mcp_servers)
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
