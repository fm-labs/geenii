# Skills

A skill is a reusable, self-contained capability packaged as a directory with a
`SKILL.md` file — following Anthropic's skill specification format. Skills add
domain knowledge, tool scoping, and executable scripts to an agent by injecting
instructions into its system prompt and optionally registering script-backed
tools.

## Anatomy of a skill

```
my-skill/
├── SKILL.md            # required: frontmatter + instructions
├── scripts/            # optional: executable scripts auto-registered as tools
│   └── fetch_data.py
└── references/         # convention: extra docs the instructions may point to
```

`SKILL.md` has YAML frontmatter and a markdown body:

```markdown
---
name: fm4-skills
description: Retrieve live track and show information from the FM4 radio station.
allowed-tools: python bash
triggers: fm4, radio, track
---

# FM4 skills

You can retrieve live FM4 data using the `fm4-skills__fm4` tool.
```

### Argument-level tool filtering

To restrict **which commands** a tool can execute, use the parameterized syntax:

```markdown
---
name: system-info
description: Gather basic system information.
allowed-tools: >-
  Bash(command:uname *), Bash(command:hostname *), Bash(command:arch *),
  Bash(command:uptime *), Bash(command:date *), Bash(command:sw_vers *),
  Bash(command:sysctl *), read
triggers: system info, sysinfo
---
```

This allows the `bash` tool only for the listed command prefixes. Any other
command (e.g. `curl`, `rm`) is blocked before execution. See
[tools.md](tools.md) for the full syntax and programmatic API.

### Frontmatter fields (`SkillSpec`, `geenii/skills.py`)

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Skill name; must match the directory name for discovery |
| `description` | yes | One-liner used for listings and skill selection |
| `metadata` | no | Free-form dict |
| `allowed-tools` | no | Comma- or space-separated list of tool access rules. Supports both plain tool names (e.g. `bash`) and argument-level filters using the syntax `ToolName(param:pattern)` where `pattern` is an fnmatch glob (e.g. `Bash(command:uname *)`). When set, the agent's available tools are narrowed to the intersection of `agent.allowed_tools` and the union of all active skills' allowed tool names. Argument-level filters additionally restrict **what arguments** a tool can be called with — blocked calls return an error without executing. Skills that omit this field inherit the full agent tool set. See [tools.md](tools.md) for details. |
| `triggers` | no | Comma- or space-separated keywords for deterministic skill activation. Matched with word boundaries against the user prompt (case-insensitive). When triggers match, the LLM selection call is skipped entirely. |

The body is the instruction text. It is loaded lazily from disk each time it is
needed, so edits take effect without restarting.

## Discovery

`skill_paths()` searches, in order:

1. `./.geenii/skills` (current working directory)
2. `$GEENII_WORKING_DIR/.geenii/skills`
3. `$GEENII_DIR/skills`
4. Every directory listed in `skill_dirs` in `geenii.json`

A skill is any subdirectory containing a `SKILL.md`. Names must be unique;
registering a duplicate name raises an error.

## How skills reach the model

1. **Loading** — an agent's `skills` list (or the CLI `--skills` override)
   loads each named skill into the agent's `SkillRegistry`.
2. **Selection** — on every prompt, `FindBestSkillTask` activates one or more
   skills on `agent.active_skills`. The selection follows a priority cascade:
   - **Single skill**: auto-selected, no LLM call.
   - **Pre-selected** (`suggested` parameter): used directly.
   - **Trigger match**: each skill's `triggers` keywords are matched against
     the prompt with word-boundary regex. Multiple skills can match
     simultaneously. No LLM call needed.
   - **LLM fallback**: a small LLM call (JSON output, temperature 0.1)
     chooses the best skill when no triggers match. The model may also
     answer "NONE".
3. **Prompt injection** — each active skill's description and full `SKILL.md`
   body are appended to the system prompt of the subsequent `LLMTask`,
   delimited by `## Skill: <name>` headers.
4. **Tool scoping** — `LLMTask` computes the effective tool set as
   `agent.allowed_tools ∩ union(skill.tool_names for each active skill)`.
   If no active skill declares `allowed-tools`, the full agent tool set is
   used. An empty intersection logs a warning. When skills use argument-level
   filters (e.g. `Bash(command:uname *)`), the tool is visible to the model
   but `ToolCallTask` enforces the argument restrictions at invocation time —
   calls that don't match any filter are rejected before execution.
5. **Script tools** — when a skill is activated, any executable files in its
   `scripts/` directory are automatically registered as tools named
   `{skill_name}__{script_stem}` (e.g. `fm4-skills__fm4`). These appear in
   the agent's tool registry and are added to `allowed_tools`, so the model
   can invoke them like any other tool. Scripts receive JSON on stdin and
   return output on stdout. See [tools.md](tools.md) for the `ScriptTool`
   class details.

Tool invocations also receive a `SKILL_NAME` environment variable containing
the comma-separated names of all active skills.

## Multi-skill composition

Multiple skills can be active simultaneously. This happens when:

- **Trigger matching** activates several skills whose keywords all appear in
  the prompt.
- **Pre-selection** passes multiple skill names.

When multiple skills are active:

- All their instructions are included in the system prompt (each under its
  own `## Skill: <name>` section).
- Tool scoping is the union of all active skills' `allowed-tools`,
  intersected with the agent's base tool set.
- Script tools from all active skills are registered.

## CLI

```bash
geenii skills list                    # all discoverable skills
geenii skills inspect <name>          # metadata; add --instructions for the body
geenii skills install <name> <source> # copy a skill into $GEENII_DIR/skills/<name>
```

`skills install` currently supports only local sources in the form
`file:///path/to/skill` (the README's URL install is not implemented yet).
Since skill instructions are executed by an agent with shell access, only
install skills from sources you trust.
