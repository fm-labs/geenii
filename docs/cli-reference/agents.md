# geenii agents

List and inspect configured agents.

## Synopsis

```
geenii agents <command>
```

## Commands

### list

```
geenii agents list
```

List all configured agents, sorted by name: first as a plain list, then as a
table with name, description (cut to 60 characters), scope, class name and
working directory. Lists the built-in agents, the agent files of the working
directory, `~/.geenii`, `/var/geenii` and `/etc/geenii`, and the agents added
by plugins and the agents of all projects registered in the user settings
(see [projects](projects.md)). `inspect` only finds the agents of the working
directory, not those of other projects.

### inspect

```
geenii agents inspect <NAME> [--instructions]
```

Show the full configuration of a named agent, including name, description,
label, model, model parameters, tools, skills, scope, working directory,
allowed directories, and (with `--instructions`) the system instructions.

### env

```
geenii agents env list <NAME>
geenii agents env set <NAME> KEY=VALUE
geenii agents env set <NAME> KEY --secret
geenii agents env unset <NAME> KEY [--secret]
```

Manage an agent's environment variables and secrets. They are passed to the
agent's tools (e.g. `bash`, `python`, skill scripts) as environment
variables; a secret with the same name as a variable wins. The values of
secrets are redacted in the tool logs.

They are stored in your user agent directory, whatever the agent's scope, so
a project's committed `.geenii/agents` never holds them:

- `~/.geenii/agents/<NAME>.vars.env` — variables
- `~/.geenii/agents/<NAME>.secrets.env` — secrets, file mode `0600`, stored as
  plain text

| Command | Does |
|---|---|
| `list NAME` | Variables with their values, and the names of the secrets (values shown as `********`) |
| `set NAME KEY=VALUE` | Set a variable. With `--secret`, store it as a secret; `set NAME KEY --secret` prompts for the value without echoing it |
| `unset NAME KEY` | Remove a variable; with `--secret`, a secret |

Names must match `[A-Za-z_][A-Za-z0-9_]*`. The agent doesn't have to exist
yet.

## See Also

- [agent](agent.md) — run an agent with a prompt
- [worker](worker.md) — run an agent unattended and send it mail
