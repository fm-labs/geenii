from openai import OpenAI
from geenii import settings

def get_openai_client():
    """
    Returns an OpenAI client instance configured with the API key from settings.

    Returns:
        OpenAI: An instance of the OpenAI client.
    """
    print("Connecting using OpenAI API Key:", settings.OPENAI_API_KEY[:8] + "..." if settings.OPENAI_API_KEY else "No API Key Found")
    return OpenAI(api_key=settings.OPENAI_API_KEY)