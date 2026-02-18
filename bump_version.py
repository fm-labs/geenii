import json
import os
import sys
sys.path.append("./src")

from geenii.utils.toml_util import read_toml, write_toml


def bump_version_json(file_path: str, key: str, new_version: str, extra: dict = None):
    #import json
    with open(file_path, "r") as f:
        data = json.load(f)

    data[key] = new_version
    print(f"Bumping version in {file_path}: {key} -> {new_version}")

    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)


def bump_version_toml(file_path: str, key: str, new_version: str, extra: dict = None):
    #import toml
    data = read_toml(file_path)

    # support nested keys like "project.version"
    keys = key.split(".")
    d = data
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = new_version

    print(f"Bumping version in {file_path}: {key} -> {new_version}")

    write_toml(file_path, data)


def bump_version_in_file(file_path: str, line_prefix: str, new_version: str, extra: dict = None):
    #if not line_prefix:
    #    print("No line prefix provided, skipping file:", file_path)
    #    return

    if not os.path.isfile(file_path):
        print("File not found, skipping:", file_path)
        return

    if extra is not None:
        if extra.get("escape") == "true":
            new_version = f"\"{new_version}\""

    with open(file_path, "r") as f:
        lines = f.readlines()

    with open(file_path, "w") as f:
        for line in lines:
            if line.startswith(line_prefix):
                f.write(f"{line_prefix} {new_version}\n")
            else:
                f.write(line)


def write_version_to_file(file_path: str, key: str, version: str, extra: dict = None):
    print(f"Writing version to {file_path}: {key} -> {version}")
    with open(file_path, "w") as f:
        f.write(version.strip() + "\n")


if __name__ == "__main__":
    # first arg from command line is the new version
    import sys
    if len(sys.argv) != 2:
        print("Usage: python bump_version.py <new_version>")
        sys.exit(1)

    new_version = sys.argv[1]
    print(f"Bumping version to: {new_version}")

    files = [
        ("pyproject.toml", "project.version", bump_version_toml, None),
        ("ui/src-tauri/Cargo.toml", "package.version", bump_version_toml, None),
        ("ui/src-tauri/tauri.conf.json", "version", bump_version_json, None),
        ("ui/package.json", "version", bump_version_json, None),
        ("src/geenii/config.py", "APP_VERSION =", bump_version_in_file, {"escape": "true"}),
        ("VERSION", "", write_version_to_file, None),
    ]
    for file_path, key, bump_func, extra in files:
        bump_func(file_path, key, new_version, extra)

    print("You need to run 'pnpm install' in the ui/ directory to update the lockfile after bumping the version.")
    print("You need to run 'pnpm tauri build' in the ui/ directory to rebuild the Tauri app after bumping the version.")
    print("You need to run 'uv sync' in the root directory to update the lockfile after bumping the version.")