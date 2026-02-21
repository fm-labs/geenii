from openai import OpenAI
from geenii import config

def get_openai_client():
    """
    Returns an OpenAI client instance configured with the API key from config.

    Returns:
        OpenAI: An instance of the OpenAI client.
    """
    print("Connecting using OpenAI API Key:", config.OPENAI_API_KEY[:8] + "..." if config.OPENAI_API_KEY else "No API Key Found")
    return OpenAI(api_key=config.OPENAI_API_KEY)