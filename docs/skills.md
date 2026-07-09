# Skills

A skill is a reusable, self-contained capability packaged as a directory with a
`SKILL.md` file — following Anthropic's skill specification format. Skills add
domain knowledge and helper scripts to an agent by injecting instructions into
its system prompt; they do not add code paths of their own.

## Anatomy of a skill

```
my-skill/
├── SKILL.md            # required: frontmatter + instructions
├── scripts/            # convention: helper scripts the instructions refer to
│   └── fetch_data.py
└── references/         # convention: extra docs the instructions may point to
```

`SKILL.md` has YAML frontmatter and a markdown body:

```markdown
---
name: fm4-skills
description: Retrieve live track and show information from the FM4 radio station.
allowed-tools: execute_python execute_command
---

# FM4 skills

To get the currently playing track, run:

    python3 $SCRIPT_DIR/fm4.py current-track
```

### Frontmatter fields (`SkillSpec`, `geenii/skills.py`)

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Skill name; must match the directory name for discovery |
| `description` | yes | One-liner used for listings and LLM-based skill selection |
| `metadata` | no | Free-form dict |
| `allowed-tools` | no | Space-separated tool names (parsed but not currently enforced) |

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
2. **Selection** — on every prompt, `FindBestSkillTask` picks at most one
   skill as `agent.selected_skill`: with a single loaded skill it is selected
   automatically; with several, a small LLM call (JSON output) chooses; the
   model may also answer "NONE".
3. **Prompt injection** — the selected skill's description and full `SKILL.md`
   body are appended to the system prompt of the subsequent `LLMTask`.
4. **Script execution** — skills typically instruct the model to run their
   scripts through the `execute_command` / `execute_python` tools. When a skill
   is selected, tool invocations receive these variables (expanded inside the
   command string):

| Variable | Value |
|---|---|
| `SKILL_NAME` | Name of the selected skill |
| `SKILL_DIR` | Absolute path of the skill directory |
| `SCRIPT_DIR` | `$SKILL_DIR/scripts` |

Only one skill is active per prompt; there is no multi-skill composition yet.

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
