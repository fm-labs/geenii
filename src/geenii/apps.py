import os

import pydantic


class GeeAppManifest(pydantic.BaseModel):
    name: str
    required_permissions: list[str] = pydantic.Field(default_factory=list)


class GeeAppSpec(pydantic.BaseModel):
    name: str
    path: str
    manifest: GeeAppManifest | None = None
    trusted: bool = False


def read_app_spec_json(file_path: str) -> GeeAppSpec:
    with open(file_path, "r") as f:
        data = f.read()
    return GeeAppSpec.model_validate_json(data)


class AppRegistry:
    def __init__(self):
        self.apps: dict[str, GeeAppSpec] = {}

    def register_app(self, app_spec: GeeAppSpec):
        self.apps[app_spec.name] = app_spec

    def get_app(self, app_name: str) -> GeeAppSpec | None:
        return self.apps.get(app_name)

    def list_apps(self) -> list[GeeAppSpec]:
        return list(self.apps.values())

    def list_app_names(self) -> list[str]:
        return list(self.apps.keys())

    def unregister_app(self, app_name: str):
        if app_name in self.apps:
            del self.apps[app_name]

    def clear_registry(self):
        self.apps.clear()

    def load_apps_from_directory(self, directory: str):
        # check all directory entries for app_spec.json files and load them
        for entry in os.listdir(directory):
            entry_path = os.path.join(directory, entry)
            if os.path.isdir(entry_path):
                app_spec_path = os.path.join(entry_path, "app.manifest.json")
                if os.path.isfile(app_spec_path):
                    try:
                        app_spec = read_app_spec_json(app_spec_path)
                        self.register_app(app_spec)
                    except Exception as e:
                        print(f"Error loading app spec from {app_spec_path}: {e}")
                else:
                    print(f"No app.manifest.json found in {entry_path}, auto-configure.")
                    app_spec = GeeAppSpec(name=entry, path=entry_path, manifest=None, trusted=False)
                    self.register_app(app_spec)
