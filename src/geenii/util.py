def split_model(model_id: str) -> tuple[str, str]:
    """
    Split the model_id string into provider and model name.
    The model string should be in the format "provider:model_name".

    :param model_id: The model identifier string.
    :return: The provider and model name as a tuple.
    """
    if ":" in model_id:
        parts = model_id.split(":", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    raise ValueError("Invalid model")


