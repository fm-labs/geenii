import logging

logger = logging.getLogger(__name__)

def estimate_token_count(input_text: str, expected_output_chars: int = 0) -> tuple[int, int, int]:
    """
    Estimate the number of tokens in the input text and expected output based on character count.

    This is a very rough estimation and can vary greatly based on the actual content and the model's tokenizer.
    A common heuristic is that 1 token is approximately 4 characters in English text, but this can vary.
    """
    input_tokens = len(input_text) // 4  # Estimate tokens in input text
    output_tokens = expected_output_chars // 4  # Estimate tokens in expected output
    total_tokens = input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


def estimate_token_cost(input_text: str, expected_output_chars: int, price_per_million_tokens: float) -> tuple[float, float, float]:
    """
    Estimate the cost of tokens for a given input and expected output based on a price per million tokens.
    """
    it,ot,tt = estimate_token_count(input_text, expected_output_chars)
    input_cost = (it/1_000_000) * price_per_million_tokens
    output_cost = (ot/1_000_000) * price_per_million_tokens
    total_cost = input_cost + output_cost
    return input_cost, output_cost, total_cost


def estimated_max_response_length(input_text: str, model_max_tokens: int, reserved_tokens: int = 100) -> int:
    """Estimate the maximum number of tokens available for the model's response based on the input text and model's context window."""
    input_tokens,_,_ = estimate_token_count(input_text)
    # Calculate the remaining tokens available for the response
    remaining_tokens = model_max_tokens - input_tokens - reserved_tokens
    # Ensure that the remaining tokens is not negative
    if remaining_tokens < 0:
        logger.warning(f"Input text is too long and may exceed the model's context window. Estimated input tokens: {input_tokens}, which exceeds the model's max tokens of {model_max_tokens} when accounting for reserved tokens.")
        return 0
    return remaining_tokens
