# geenii skills

List, inspect, and install skills.

## Synopsis

```
geenii skills <command>
```

## Commands

### list

```
geenii skills list
```

List all registered skills with their descriptions.

### inspect

```
geenii skills inspect <NAME> [OPTIONS]
```

Show details for a specific skill, including name, path, description, metadata,
and allowed tools.

#### Options

| Option | Short | Description |
|---|---|---|
| `--instructions` | `-i` | Print the full SKILL.md instructions body |

### install

```
geenii skills install <NAME> <SOURCE>
```

Install a skill from a source. Currently only local file sources are supported.

#### Arguments

| Argument | Description |
|---|---|
| `NAME` | Name to install the skill as |
| `SOURCE` | Source URI (`file:///path/to/skill`) |

#### Examples

```bash
geenii skills list
geenii skills inspect my-skill -i
geenii skills install my-skill file:///home/user/skills/my-skill
```
