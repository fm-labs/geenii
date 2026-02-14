import os


def read_toml(path: str) -> dict:
    with open(path, "rb") as f:
        content = f.read()

    # Prefer stdlib tomllib if available (Python 3.11+)
    try:
        import tomllib  # type: ignore
        data = tomllib.loads(content.decode("utf-8"))
    except ModuleNotFoundError:
        try:
            import toml  # type: ignore
        except ModuleNotFoundError:
            raise RuntimeError("Error: Need 'tomllib' (Python 3.11+) or 'toml' package to read TOML.")
        data = toml.loads(content.decode("utf-8"))
    if not isinstance(data, dict):
        data = {}
    return data


def write_toml(path: str, data: dict) -> None:
    print(f"Writing TOML data to {path}...")

    dirpath = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(dirpath, exist_ok=True)

    try:
        import tomli_w
        with open(path, "wb") as f:
            tomli_w.dump(data, f)
    except ModuleNotFoundError:
        try:
            import toml  # type: ignore
        except ModuleNotFoundError:
            raise RuntimeError("Error: Need 'tomli-w' or 'toml' package to write TOML.")
        with open(path, "w") as f:
            f.write(toml.dumps(data))