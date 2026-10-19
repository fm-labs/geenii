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
working directory. Includes the agents of all projects registered in the user
settings (see [projects](projects.md)).

### inspect

```
geenii agents inspect <NAME>
```

Show the full configuration of a named agent, including name, description,
label, model, model parameters, tools, skills, scope, working directory,
allowed directories, and (with `--instructions`) the system instructions.

## See Also

- [agent](agent.md) — run an agent with a prompt
