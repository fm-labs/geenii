# Creating a new release


## Checklist

- [ ] Bump version number in `ui/package.json`
- [ ] Bump version number in `ui/src-tauri/tauri.conf.json`
- [ ] Bump version number in `ui/src-tauri/Cargo.toml`
- [ ] Bump version number in `src/geenii/settings.py`
- [ ] Update `CHANGELOG.md` with the changes in the new release
- [ ] Create a git commit with the changes and push to the repository
- [ ] Create a new tag for the new release and push the tag to the repository

-> There is `bump_version.py` helper script that can be used to automate this process. 
It will update the version number in all the necessary files and create a git commit with the changes.

```bash
uv run bump_version.py <new_version>
```


## Building the app

### Building the python sidecar binaries

Binaries for the python sidecar can be built using the `build_bin.sh`helper script.
This will create a `dist/bin` directory with the built binaries for the respective platform you are building on. 

- On Linux, MacOS: Outputs `geeniid` and `geenii` binaries
- On Windows: Outputs `geeniid.exe` and `geenii.exe` binaries


### Building the web app

The web app can be built using the following command:

```bash
cd ui
pnpm install --frozen-lockfile
pnpm run build
```

### Building the desktop app

The desktop app can be built using the following command:

```bash
cd ui
pnpm install --frozen-lockfile
pnpm tauri build
```

- On Linux, this will output a `target/release/bundle` directory with the built AppImage, deb, and rpm packages.
- On MacOS, this will output a `target/release/bundle` directory with the built .dmg and .app packages.
  - `dmg`: Outputs a file in the format `dmg/geenii-desktop-<version>-<aarch64|x86_64>.dmg`
  - `app`: Outputs a file in the format `macos/geenii-desktop.app.tar.gz` (+ sig)
- On Windows, this will output a `target/release/bundle` directory with the built .exe installer and .msi installer packages.
  - `exe`: Not supported yet
  - `msi`: Not supported yet


#### Host triple naming convention

The host triples used in the release artifacts follow the rustc naming convention, which is in the format of `<arch>-<vendor>-<os>`.

Sidecar binaries follow the same naming convention, but with an additional `-gnu` suffix for Linux binaries 
to indicate that they are linked against the GNU C library.

Following are the host triples used for the release artifacts:

| Host Triple                 | Architecture | Vendor | Operating System | Target Platform |
|-----------------------------|--------------|--------|------------------|-----------------|
| `x86_64-unknown-linux-gnu`  | x86_64       |        | unknown          | Linux           |
| `aarch64-unknown-linux-gnu` | aarch64      |        | unknown          | Linux           |
| `x86_64-apple-darwin`       | x86_64       | apple  | macOS            | MacOS           |
| `aarch64-apple-darwin`      | aarch64      | apple  | macOS            | MacOS           |
| `x86_64-pc-windows-msvc`    | x86_64       | pc     | windows          | Windows         |
| `aarch64-pc-windows-msvc`   | aarch64      | pc     | windows          | Windows         | 