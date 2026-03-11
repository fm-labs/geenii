import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator, Set

from geenii.agent.base import BaseAgentTask, BaseTask, message_to_prompt
from geenii.agent.utils import estimate_token_count
from geenii.ai import generate_chat_completion
from geenii.chat.chat_models import UserInteractionContent, ToolCallResultContent, ContentPart, TextContent, \
    ToolCallContent, JsonContent
from geenii.datamodels import ModelMessage, ChatCompletionRequest
from geenii.g import init_agent_registry, init_agent_by_name
from geenii.tool.registry import ToolRegistry
from geenii.utils.json_util import parse_json_safe

logger = logging.getLogger(__name__)

class ToolCallTask(BaseAgentTask):
    def __init__(self, agent: "BaseAgent", tool_name: str, arguments: dict, call_id: str = None):
        super().__init__(agent)
        self.tool_name = tool_name
        self.arguments = arguments
        self.call_id = call_id

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:
        tool_name = self.tool_name
        arguments = self.arguments
        call_id = self.call_id
        selected_skill = self.agent.selected_skill

        # yield a message, requesting approval for the tool call before executing it
        tool_usage_request_message = ModelMessage(role="assistant", content=[
            UserInteractionContent(
                interaction_id=call_id,
                interaction_type="tool_call_request",
                text=f"Requesting approval to call tool '{tool_name}' with arguments {arguments} and call ID '{call_id}'.",
                choices=["Allow", "Deny"],
            )])
        yield tool_usage_request_message

        tool_usage_approved = await self.agent.request_tool_execution(tool_name=tool_name, arguments=arguments,
                                                                      call_id=call_id)
        if not tool_usage_approved:
            logger.critical(f"Tool execution for {tool_name} was rejected by the request_tool_execution method.")
            tool_result = {"error": "Tool execution rejected."}
            msg = ModelMessage(role="tool", content=[
                ToolCallResultContent(name=tool_name, arguments=arguments, result=tool_result, call_id=call_id)])
            yield msg
            self.agent.message_history.append(msg)
            return

        logger.info(f"Calling tool {tool_name} with arguments {arguments}")
        try:
            #tool_result = await execute_tool_call(self.agent.tools, tool_name=tool_name, args=arguments)
            tool = self.agent.tools.get(tool_name)
            if tool is None:
                raise ValueError(f"Tool {tool_name!r} is not registered")
            #logger.info(f'EXECUTING TOOL "{tool_name}" with args {arguments}')

            tool_env = {
                "SKILL_NAME": selected_skill or "",
                "SKILL_DIR": f"{self.agent.skills.get(selected_skill).path}" if selected_skill else "",
            }
            tool_result = await tool.invoke(args=arguments, env=tool_env)

            logger.info(f"Tool {tool_name} returned result: {tool_result}")
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}", exc_info=e)
            tool_result = {"error": str(e)}
        msg = ModelMessage(role="tool", content=[
            ToolCallResultContent(name=tool_name, arguments=arguments, result=tool_result, call_id=call_id)])
        yield msg
        self.agent.message_history.append(msg)


class LLMTask(BaseAgentTask):
    """Generate LLM chat completion response in the current context. Handles tool calls"""

    MAX_TOOL_CALLS = 5  # to prevent infinite loops of tool calls

    def __init__(self, agent: "BaseAgent", message: str | list[ContentPart], allowed_tools: Set[str] | None = None):
        super().__init__(agent)
        self.message = message
        self.allowed_tools = allowed_tools
        if self.allowed_tools is None:
            self.allowed_tools = set(self.agent.allowed_tools)

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:
        full_system_prompt = self._build_system_prompt()
        # print(full_system_prompt)
        prompt = message_to_prompt(self.message)
        allowed_tools = self.allowed_tools
        input_messages = list(self.agent.message_history[-10:]) # message history (max 10 messages)

        # run sync task in thread pool to avoid blocking the event loop while waiting for the response
        request = ChatCompletionRequest(prompt=prompt,
                                        model=self.agent.model,
                                        system=full_system_prompt,
                                        messages=input_messages,
                                        tools=allowed_tools,
                                        context_id=self.agent.context_id
                                        )
        response = await asyncio.to_thread(self._request_completion, request)
        logger.info(f"Received model response for prompt '{prompt}' with {len(response.output)} content parts.")

        # add user request to message history
        if prompt and len(prompt.strip()) > 0:
            user_message = ModelMessage(role="user", content=[TextContent(text=prompt)])
            self.agent.message_history.append(user_message)

        # add model response to message history
        bot_message = ModelMessage(role="assistant", content=response.output)
        self.agent.message_history.append(bot_message)

        # yield the model response message
        yield bot_message

        # handle tools calls
        tools_called = 0
        while True:
            tool_call_contents = [content for content in response.output if isinstance(content, ToolCallContent)]
            logger.warning(f"Detected {len(tool_call_contents)} tool calls in the model response.")
            if len(tool_call_contents) < 1:
                if tools_called == 0:
                    logger.info("No tool calls detected in the model response. Proceeding to yield the final response.")
                break  # no tool calls, we can proceed without re-generating the response.

            if tools_called > self.MAX_TOOL_CALLS:
                logger.error(f"Too many tool calls detected in the response. Stopping further processing to avoid infinite loops.")
                yield ModelMessage(role="assistant", content=[TextContent(text=f"Error: Too many tool calls detected in the response. Stopping further processing.")])
                break

            # handle the first tool call in the response and then re-generate the response based on the tool result,
            # until there are no more tool calls in the response
            tool_call = tool_call_contents.pop(0)
            logger.warning(f"Next tool call to process: {tool_call.name} with arguments {tool_call.arguments} and call ID {tool_call.call_id}")
            tool_task = ToolCallTask(agent=self.agent, tool_name=tool_call.name, arguments=tool_call.arguments, call_id=tool_call.call_id)
            tool_result = None
            async for msg in tool_task.execute():
                if isinstance(msg, ModelMessage) and isinstance(msg.content[0], ToolCallResultContent):
                    tool_result = msg.content[0].result
                    # add the tool result to the message history so that it can be used as context for the next response generation
                    self.agent.message_history.append(msg)
                else:
                    # if the tool task yields any other messages (e.g. user interaction requests), we yield them immediately
                    # todo: add to message history as well?
                    yield msg

            tools_called += 1
            if tool_result is not None:
                # re-generate the response based on the tool result
                tool_result_message = ModelMessage(role="assistant", content=[TextContent(text=f"Tool '{tool_call.name}' returned result: {tool_result}")])
                self.agent.message_history.append(tool_result_message)

                # now we can re-generate the response based on the original prompt and the updated message history that includes the tool result
                request.prompt = ""
                request.messages = list(self.agent.message_history[-((tools_called*2) + 3):])  # snapshot of the updated message history
                response = await asyncio.to_thread(self._request_completion, request)
                logger.info(f"Received model response for prompt '{prompt}' after tool call with {len(response.output)} content parts.")
            else:
                logger.error(f"Tool call {tool_call.name} did not return a valid result. Skipping re-generation of the response.")
                yield ModelMessage(role="assistant", content=[TextContent(text=f"Tool '{tool_call.name}' did not return a valid result.")])
                break  # if the tool call did not return a valid result, we stop the process to avoid infinite loops

        # if there were tool calls, trigger a follow-up action,
        # to ask the LLM for the next step based on the tool results.
        if tools_called > 0:
            logger.info(
                f"{tools_called} tool calls were made in the response. Enqueuing follow-up task to process tool results.")
            #await self.agent.enqueue_task(FinalizeTask(self.agent))
            await self.agent.enqueue_task(LLMTask(self.agent,
                          message="Based on the tool results, continue processing the original prompt and provide the next response.",
                          allowed_tools=allowed_tools))

    def _request_completion(self, request):
        response = generate_chat_completion(request=request, tool_registry=self.agent.tools, )
        return response

    def _build_system_prompt(self) -> list[str]:
        """
        Build the full system prompt for the agent, including the base system prompt and any additional information from loaded skills.
        """
        current_datetime = datetime.now().isoformat()
        agent_context_info = "\n".join(["CONTEXT INFORMATION:",
                          f"Current conversation context ID: {self.agent.context_id}",
                          f"Current date and time: {current_datetime}"])

        system_prompts = [self.agent.system_prompt, agent_context_info]
        skills_prompts = self._build_skills_prompt()
        system_prompts.extend(skills_prompts)
        return system_prompts

    def _build_skills_prompt(self) -> list[str]:
        """
        Returns a combined prompt for all loaded skills that can be included in the system prompt
        to provide the agent with information about its skills and how to use them.
        :return:
        """
        skills_prompts = []
        if not self.agent.skills or len(self.agent.skills.names()) == 0:
            return skills_prompts
        #for skill_name in self.agent.skills.list_skill_names():
        if self.agent.selected_skill:
            skill_name = self.agent.selected_skill
            skill = self.agent.skills.get(skill_name)
            if skill:
                skills_prompt = f"You have a special skill named {skill_name}:\n"
                skills_prompt += f"{skill.description}\n"
                skills_prompt += f"Skill Instructions:\n{skill.instructions}\n\n"
                skills_prompts.append(skills_prompt)
        return skills_prompts


# class FinalizeTask(BaseAgentTask):
#     def __init__(self, agent: "BaseAgent"):
#         super().__init__(agent)
#
#     async def execute(self) -> AsyncGenerator[ModelMessage | BaseTask, None]:
#         #yield ModelMessage(role="assistant",
#         #                   content=[TextContent(text=f"Finalizing response after processing tool results.")])
#         yield LLMTask(self.agent, message="Based on the tool results, continue processing the original prompt and provide the next response.",
#                       allowed_tools=set())


class ToolFilterTask(BaseAgentTask):
    """Task to find the best-suitable tool to call based on the current message and context"""

    SYSTEM_PROMPT = """
    You are an AI tool orchestrator. Given a user prompt you must:
    1. Select the best-fit agent(s) from the provided list.
    2. Produce a short execution plan.

    Always respond with valid JSON in exactly this shape:
    {
      "tools":       ["<tool>", ...],
      "confidence":   <0.0-1.0>
    }

    If nothing fits well, pick the closest options and lower the confidence score.
    """.strip()

    OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "tools": {
                "type": "array",
                "items": {"type": "string"}
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
        },
        "required": ["tools", "confidence"],
        "additionalProperties": False
    }

    def __init__(self, agent: "BaseAgent", prompt: str, tool_registry: ToolRegistry):
        super().__init__(agent)
        self.prompt = prompt
        self.tool_registry = tool_registry

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:

        tools_str = "\n".join([f"- {tool_name}: {self.tool_registry.get_tool_description(tool_name)}" for tool_name in
                               self.tool_registry.list_tool_names()])

        request = ChatCompletionRequest(
            model=self.agent.model,
            model_parameters={"temperature": 0.1, "max_tokens": 512},
            system=[self.SYSTEM_PROMPT, f"Available tools:\n{tools_str}"],
            prompt=self.prompt,
            messages=[],
            output_format="json",
            output_schema=self.OUTPUT_SCHEMA,
            # tools=tool_names,
        )
        response = await asyncio.to_thread(generate_chat_completion, request)
        logger.info(f"Received model response for tool filtering with {len(response.output)} content parts.")
        selected_tools = []
        if len(response.output) > 0:
            if isinstance(response.output[0], JsonContent):
                parsed = response.output[0].data
                if parsed and "tools" in parsed and isinstance(parsed["tools"], list):
                    selected_tools = parsed["tools"]
                    logger.info(
                        f"Tool filter selected tools: {selected_tools} with confidence {parsed.get('confidence', 'N/A')}")
            if isinstance(response.output[0], TextContent):
                parsed = parse_json_safe(response.output[0].text)
                if parsed and "tools" in parsed and isinstance(parsed["tools"], list):
                    selected_tools = parsed["tools"]
                    logger.info(
                        f"Tool filter selected tools: {selected_tools} with confidence {parsed.get('confidence', 'N/A')}")

        # now update the agent's tool registry to only allow the selected tools for the next LLM response
        # self.agent.set_allowed_tools(selected_tools)
        # yield WizModMessage(self.agent, allowed_tools=selected_tools)

        # yield a no-op message just to trigger the next step in the process
        yield ModelMessage(role="assistant", content=[TextContent(text=f"Selected tools: {', '.join(selected_tools)}")])


class HandoffTask(BaseAgentTask):
    """Task to hand off the conversation to another agent or agent"""

    def __init__(self, agent: "BaseAgent", target_agent_name: str, prompt: str = None):
        super().__init__(agent)
        self.target_agent_name = target_agent_name
        self.prompt = prompt or f"Handing off the conversation to {target_agent_name}."

        sub = init_agent_by_name(target_agent_name)
        if not sub:
            raise ValueError(f"Target agent '{target_agent_name}' not found for handoff.")
        self.sub = sub
        self.sub._hidl = self.agent._hidl  # share the same human-in-the-loop handler

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:
        # This is a placeholder implementation. In a real implementation, you would look up the target agent by name,
        # transfer the conversation context and message history to the target agent, and yield a message indicating the handoff.
        msg = ModelMessage(role="assistant",
                           content=[TextContent(text=f"Handing off conversation to {self.target_agent_name}.")])
        self.agent.message_history.append(msg)

        # todo transfer conversation context and message history
        #self.sub.message_history.extend(list(self.agent.message_history[-6:]))  # transfer last 6 messages as context

        async for msg in self.sub.prompt(self.prompt):
            yield msg


class FindBestAgentTask(BaseAgentTask):
    """Find the best-suitable agent to handle the current conversation based on the current message and context"""

    SYSTEM_PROMPT = """
    You are an AI agent selector. Given a user prompt and conversation context, you must:
    1. Select the best-fit agent from the provided list.
    2. Double-check if the selected agent is on the list.
    3. Provide a brief rationale for your choice.
    
    The list includes a brief description of each agent's capabilities and purpose to help you make an informed decision.
    Format:
    - <agent_name>: <brief description of the agent's purpose>

    Rules:
    - Always select the agent that is best suited to handle the user's request based on its capabilities and the conversation context.
    - Only produce a final answer with the selected agent's name and rationale. Do not list multiple agents or provide any other information.

    Always respond with valid JSON in exactly this shape:
    {
      "agent":       "<agent_name>",
      "confidence":   <0.0-1.0>,
      "rationale":    "<brief explanation of why this agent is the best fit>"
    }

    If no agent fits well, pick the closest option or 'NONE' and lower the confidence score.
    """.strip()

    OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "agent": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "rationale": {"type": "string"}
        },
        "required": ["agent", "confidence", "rationale"],
        "additionalProperties": False
    }

    def __init__(self, agent: "BaseAgent", prompt: str):
        super().__init__(agent)
        self.prompt = prompt
        self.agent_registry = init_agent_registry(auto_load=True)

    async def execute(self) -> AsyncGenerator[ModelMessage | BaseTask, None]:
        available_agents = []
        for agent in self.agent_registry._agent_configs.values():
            if agent.name == "default":
                continue  # skip default agent
            description = agent.description or "No description available."
            tools = ", ".join(agent.tools) if agent.tools else "No tools"
            skills = ", ".join(agent.skills) if agent.skills else "No special skills"
            agent_info = f"{agent.name}: {description} using Tools: {tools}"
            available_agents.append(agent_info)
        agents_str = "\n - ".join(available_agents)

        request = ChatCompletionRequest(
            model=self.agent.model,
            model_parameters={"temperature": 0.1, "max_tokens": 512},
            system=[self.SYSTEM_PROMPT, f"Available agents:\n{agents_str}"],
            prompt=self.prompt,
            messages=[],
            output_format="json",
            output_schema=self.OUTPUT_SCHEMA,
        )
        response = await asyncio.to_thread(generate_chat_completion, request)
        logger.info(f"Received model response for agent selection with {len(response.output)} content parts.")
        selected_agent = None
        if len(response.output) > 0:
            parsed = None
            if isinstance(response.output[0], JsonContent):
                parsed = response.output[0].data
            if isinstance(response.output[0], TextContent):
                parsed = parse_json_safe(response.output[0].text)

            logger.info(parsed)
            if parsed and "agent" in parsed and isinstance(parsed["agent"], str):
                selected_agent = parsed["agent"]
                logger.info(
                    f"Agent selector selected agent: {selected_agent} with confidence {parsed.get('confidence', 'N/A')}. Rationale: {parsed.get('rationale', 'N/A')}")

        if selected_agent and selected_agent.strip().lower() == "none":
            selected_agent = None

        if selected_agent:
            yield ModelMessage(role="assistant", content=[TextContent(
                text=f"Selected agent: {selected_agent} with confidence {parsed.get('confidence', 'N/A')}. Rationale: {parsed.get('rationale', 'N/A')}")])
            yield HandoffTask(self.agent, target_agent_name=selected_agent, prompt=self.prompt)

        else:
            yield ModelMessage(role="assistant", content=[TextContent(text=f"No suitable agent found. Trying to process the prompt with the current agent.")])
            yield LLMTask(self.agent, message=self.prompt)  # fallback to processing the prompt with the current agent


class FindBestSkillTask(BaseAgentTask):
    """Find the best-suitable skill to handle the current conversation based on the current message and context"""

    SYSTEM_PROMPT = """
    You are specialized in selecting the best skill from a list to fulfill a task. Given a user prompt and conversation context, you must:
    1. Select the best-fit skill from the provided list.
    2. Provide a brief rationale for your choice.

    The list includes a brief description of each skill's capabilities and purpose to help you make an informed decision.
    Format:
    - <skill_name>: <brief description of the skill's purpose>

    Rules:
    - Always select the skill that is best suited to handle the user's request based on its capabilities and the conversation context.
    - Only produce a final answer with the selected skill's name and rationale. Do not list multiple skills or provide any other information.

    Always respond with valid JSON in exactly this shape:
    {
      "skill":       "<skill_name>",
      "confidence":   <0.0-1.0>,
      "rationale":    "<brief explanation of why this skill is the best fit>"
    }

    If no skill fits well, pick the closest option or 'NONE' and lower the confidence score.
    """.strip()

    OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "skill": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "rationale": {"type": "string"}
        },
        "required": ["skill", "confidence", "rationale"],
        "additionalProperties": False
    }

    def __init__(self, agent: "BaseAgent", prompt: str, suggested: str | None = None):
        super().__init__(agent)
        self.prompt = prompt
        self.suggested = suggested # pre-selected skills

    async def execute(self) -> AsyncGenerator[ModelMessage | BaseTask, None]:

        if len(self.agent.skills.skills) == 0:
            #yield ModelMessage(role="assistant", content=[TextContent(text=f"No skills are currently loaded. Trying to process the prompt without a special skill.")])
            logger.info("No skills available.")
            return

        elif len(self.agent.skills.skills) == 1:
            selected_skill = self.agent.skills.names().pop()
            #yield ModelMessage(role="assistant", content=[TextContent(
            #    text=f"Only one skill available. Selected skill: {selected_skill}.")])
            self.agent.selected_skill = selected_skill
            logger.info("Selected skill the only skill: %s", selected_skill)
            return

        if self.suggested and len(self.suggested) == 1:
            selected_skill = self.suggested[0]
            self.agent.selected_skill = selected_skill
            logger.info("Selected skill from pre-selection: %s", selected_skill)
            return

        available_skills = []
        for skill_name in self.agent.skills.names():
            skill = self.agent.skills.get(skill_name)
            description = skill.description or "No description available."
            #tools = ",".join(skill.tools) if skill.tools else "No tools"
            skill_info = f"{skill_name}: {description}"
            available_skills.append(skill_info)

        skills_str = "\n - ".join(available_skills)
        request = ChatCompletionRequest(
            model=self.agent.model,
            model_parameters={"temperature": 0.1, "max_tokens": 512},
            system=[self.SYSTEM_PROMPT, f"Available skills:\n{skills_str}"],
            prompt=self.prompt,
            messages=[],
            output_format="json",
            output_schema=self.OUTPUT_SCHEMA,
        )
        response = await asyncio.to_thread(generate_chat_completion, request)
        logger.info(f"Received model response for agent selection with {len(response.output)} content parts.")

        selected_skill = None
        if len(response.output) > 0:
            parsed = None
            if isinstance(response.output[0], JsonContent):
                parsed = response.output[0].data
            if isinstance(response.output[0], TextContent):
                parsed = parse_json_safe(response.output[0].text)

            logger.info(parsed)
            if parsed and "skill" in parsed and isinstance(parsed["skill"], str):
                selected_skill = parsed["skill"]
                logger.info(
                    f"Agent selector selected agent: {selected_skill} with confidence {parsed.get('confidence', 'N/A')}. Rationale: {parsed.get('rationale', 'N/A')}")

            if selected_skill and selected_skill.strip().lower() == "none":
                selected_skill = None

            if selected_skill:
                yield ModelMessage(role="assistant", content=[TextContent(
                    text=f"Selected skill: {selected_skill} with confidence {parsed.get('confidence', 'N/A')}. Rationale: {parsed.get('rationale', 'N/A')}")])
            else:
                yield ModelMessage(role="assistant", content=[TextContent(text=f"No suitable skill found. Trying to process the prompt without a special skill.")])
            self.agent.selected_skill = selected_skill


class PlanTask(BaseAgentTask):
    """
    Task to create a multi-step plan for a complex task that requires multiple steps, skills or tool calls.
    Based on the current message and context, the agent should break down the task into a clear, step-by-step plan.
    Uses the agents tools and skills information to determine if any steps require specific tools or skills and includes that information in the plan.
    Returns a structured plan that can be executed step by step, with explicit mentions of any required tools or skills for each step.
    The output should be in a structured format that can be easily parsed and executed
    """

    SYSTEM_PROMPT = """
You are an expert planner agent. Your task is to create a clear, step-by-step plan to accomplish a complex task based on the user's request and the conversation context.

Workflow:
1. Break down the task into clear, sequential steps.
2. For each step, explicitly mention the skill to be used to accomplish that step. The steps MUST be in the list of skills available to the agent. If no special skill is required for a step, use "None" or leave empty.
4. Ensure the plan is actionable and can be executed step by step.
5. Always respond with a structured plan in JSON format with the following shape:
{
  "plan": [
    {
      "step": "<description of the step>",
      "skill": "<skill_name>"  // optional name of the required skill for this step, can be "None" or empty if no special skill is needed
    },
    ...
  ]
}

If the task is simple and does not require multiple steps, return a plan with a single step that describes the action to be taken.

AVAILABLE SKILLS:
{{{skills_list}}}
""".strip()

    def __init__(self, agent: "BaseAgent", prompt: str):
        super().__init__(agent)
        self.prompt = prompt


    def _build_tools_list(self) -> str:
        if not self.agent.tools or len(self.agent.tools.list_tool_names()) == 0:
            return "No tools available."

        enabled_tools_list = []
        for tool_name in self.agent.tools.list_tool_names():
            if tool_name in self.agent.allowed_tools:
                enabled_tools_list.append(f"- {tool_name}: {self.agent.tools.get(tool_name).description} (enabled)")
            else:
                #enabled_tools_list.append(f"- {tool_name}: {self.agent.tools.get(tool_name).description} (disabled)")
                pass  # skip disabled tools in the list to avoid confusion
        return "\n".join(enabled_tools_list)

    def _build_skills_list(self) -> str:
        if not self.agent.skills or len(self.agent.skills.names()) == 0:
            return "No skills available."
        return "\n".join([f"- {skill_name}: {self.agent.skills.get(skill_name).description}" for skill_name in self.agent.skills.names()])

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:
        tools_list = self._build_tools_list()
        skills_list = self._build_skills_list()
        system_prompt = self.SYSTEM_PROMPT.replace("{{{tools_list}}}", tools_list).replace("{{{skills_list}}}", skills_list)

        print("***" * 10)
        print(system_prompt)
        print("***" * 10)
        print(estimate_token_count(system_prompt, 1000))
        print("***" * 10)

        request = ChatCompletionRequest(
            model=self.agent.model,
            model_parameters={"temperature": 0.1, "max_tokens": 1024},
            system=[system_prompt],
            prompt=self.prompt,
            messages=[],
            output_format="json",
            output_schema={
                "type": "object",
                "properties": {
                    "plan": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "step": {"type": "string"},
                                "skill": {"type": "string"}
                            },
                            "required": ["step"],
                            "additionalProperties": False
                        }
                    }
                },
                "required": ["plan"],
                "additionalProperties": False
            }
        )
        response = await asyncio.to_thread(generate_chat_completion, request)
        logger.info(f"Received model response for plan generation with {len(response.output)} content parts.")

        if len(response.output) > 0:
            if isinstance(response.output[0], JsonContent):
                parsed = response.output[0].data
                if parsed and "plan" in parsed and isinstance(parsed["plan"], list):
                    plan = parsed["plan"]
                    #yield ModelMessage(role="assistant", content=[JsonContent(data={"plan": plan})])
                    #self.agent.message_history.append(ModelMessage(role="assistant", content=[JsonContent(data={"plan": plan})]))

                    # execute the plan step by step, yielding messages for each step and handling any required skills or tools
                    for idx, item in enumerate(plan):
                        step_description = item.get("step", "")
                        suggested_skills = []
                        skill = item.get("skill", None)
                        if skill and skill.lower() != "none":
                            suggested_skills.append(skill.lower())

                        yield ModelMessage(role="assistant", content=[
                            TextContent(text=f"Step {idx + 1}: {step_description} (suggested skill: {skill})")])

                        # nevertheless, try to find the best skill, but we add the suggested skill as a hint in the prompt for the FindBestSkillTask
                        yield FindBestSkillTask(self.agent,
                                                prompt=f"For the following step in the plan: '{step_description}', select the best skill to accomplish this step from the available skills.",
                                                suggested=suggested_skills)
                        yield LLMTask(self.agent, message=f"Execute the step: '{step_description}' using the selected skill.")
                        # todo tool suggestions for LLMTask

                else:
                    logger.error("PlanTask: Invalid plan format in model response.")
            else:
                logger.error("PlanTask: Expected JSON content in model response.")
        else:
            logger.error("PlanTask: No content in model response.")




# class AnonymousTask(BaseTask):
#     def __init__(self, fn: Callable[[], AsyncGenerator[ModelMessage, None]]):
#         self.fn = fn
#
#     async def run(self) -> AsyncGenerator[ModelMessage, None]:
#         async for msg in self.fn():
#             yield msg
