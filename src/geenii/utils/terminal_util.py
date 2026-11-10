import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap


def open_terminal(command: str | None = None, keep_open: bool = True, cwd: str | None = None):
    """Open a new terminal window, optionally running `command` in it."""
    cwd = cwd or os.getcwd()

    # ---------------- macOS ----------------
    if sys.platform == "darwin":
        script = f"cd {shlex.quote(cwd)}"
        if command:
            script += f"\n{command.strip()}"
        if not keep_open:
            script += "\nexit"
        # Escape for an AppleScript string literal
        as_str = script.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(
            [
                "osascript",
                "-e",
                f'tell application "Terminal" to do script "{as_str}"',
                "-e",
                'tell application "Terminal" to activate',
            ]
        )
        return

    # ---------------- Windows ----------------
    if sys.platform == "win32":
        flag = "/k" if keep_open else "/c"
        args = ["cmd", flag, command] if command else ["cmd"]
        subprocess.Popen(args, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        return

    # ---------------- Linux / BSD ----------------
    shell = os.environ.get("SHELL", "/bin/bash")
    if command:
        inner = f"{command.strip()}\nexec {shell}" if keep_open else command.strip()
        run = [shell, "-c", inner]
    else:
        run = [shell]

    # (name, how to pass the command)
    candidates = [
        (os.environ.get("TERMINAL"), ["-e"]),
        ("x-terminal-emulator", ["-e"]),  # Debian/Ubuntu "default terminal"
        ("gnome-terminal", ["--"]),
        ("konsole", ["-e"]),
        ("xfce4-terminal", ["-x"]),
        ("kitty", []),
        ("alacritty", ["-e"]),
        ("wezterm", ["start", "--"]),
        ("foot", []),
        ("xterm", ["-e"]),
    ]
    for term, prefix in candidates:
        if term and shutil.which(term):
            p = subprocess.Popen([term, *prefix, *run], cwd=cwd, start_new_session=True)
            pid = p.pid
            print(f"Started {term} with PID {pid}")
            return
    raise RuntimeError("No terminal emulator found")


def open_terminal_script(script: str, keep_open=True, cwd=None):
    script = textwrap.dedent(script).strip() + "\n"
    if sys.platform == "win32":
        fd, path = tempfile.mkstemp(suffix=".bat")
        with os.fdopen(fd, "w") as f:
            f.write("@echo off\r\n" + script.replace("\n", "\r\n"))
        open_terminal(f'"{path}"', keep_open=keep_open, cwd=cwd)
    else:
        fd, path = tempfile.mkstemp(suffix=".sh")
        with os.fdopen(fd, "w") as f:
            f.write("#!/usr/bin/env bash\nset -eu\n" + script)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        open_terminal(shlex.quote(path), keep_open=keep_open, cwd=cwd)


if __name__ == "__main__":
    # open_terminal("ls -lah")

    #     multiline_cmd = """\
    # bash <<'EOF'
    # echo "foo"
    # sleep 3
    # ls -la
    # EOF
    # """
    #     open_terminal(multiline_cmd)

    open_terminal_script("""
        echo "foo"
        for i in 1 2 3; do echo "line $i"; done
    """)
