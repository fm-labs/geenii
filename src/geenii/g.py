from geenii.agents import init_agent_by_name
from geenii.chat.chat_bots import BotInterface


def get_bot(botname: str) -> BotInterface:
    # return EchoBot(botname=botname)
    # return SimpleBot(botname=botname)
    # return DemoAgent(botname=botname)

    if not botname.startswith("geenii:bot:"):
        raise ValueError(f"Invalid bot name: {botname}. Bot names must start with 'geenii:bot:'")

    name = botname[len("geenii:bot:"):]
    return init_agent_by_name(name)
