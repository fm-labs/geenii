import json
import toml

def bump_version_json(file_path: str, key: str, new_version: str):
    #import json
    with open(file_path, "r") as f:
        data = json.load(f)

    data[key] = new_version
    print(f"Bumping version in {file_path}: {key} -> {new_version}")

    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)


def bump_version_toml(file_path: str, key: str, new_version: str):
    #import toml
    with open(file_path, "r") as f:
        data = toml.load(f)

    # support nested keys like "project.version"
    keys = key.split(".")
    d = data
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = new_version

    print(f"Bumping version in {file_path}: {key} -> {new_version}")

    with open(file_path, "w") as f:
        toml.dump(d, f)


def bump_version_in_file(file_path: str, line_prefix: str, new_version: str):
    with open(file_path, "r") as f:
        lines = f.readlines()

    with open(file_path, "w") as f:
        for line in lines:
            if line_prefix and line.startswith(line_prefix):
                f.write(f"{line_prefix} {new_version}\n")
            else:
                f.write(line)



if __name__ == "__main__":
    # first arg from command line is the new version
    import sys
    if len(sys.argv) != 2:
        print("Usage: python bump_version.py <new_version>")
        sys.exit(1)

    new_version = sys.argv[1]
    print(f"Bumping version in {sys.argv[1]}: {new_version}")

    files = [
        ("pyproject.toml", "project.version", bump_version_toml),
        ("ui/package.json", "version", bump_version_json),
        ("src/geenii/settings.py", "APP_VERSION =", bump_version_in_file),
        ("VERSION", "", bump_version_in_file),
    ]
    for file_path, key, bump_func in files:
        bump_func(file_path, key, new_version)