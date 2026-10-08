# Using these skills with other agents

Nothing here is specific to Claude Code. A skill is a Markdown file of
instructions plus a script, and any agent that can read a file and run a shell
command can use it.

## Layout

```
skills/<name>/
├── SKILL.md              instructions — the thing to load into context
├── scripts/              dependency-free Python, run via shell
└── references/           longer docs SKILL.md points at, loaded on demand
```

`SKILL.md` opens with YAML frontmatter holding `name` and `description`. The
description is the trigger: it says when the skill applies. The body is written
for a capable model — it explains *why* each step matters rather than issuing
rules, because a model that understands the reasoning handles the cases the
instructions did not anticipate.

## Wiring one up

**Cursor / Windsurf / Copilot-style rules files**: copy or symlink `SKILL.md`
into the rules directory. Keep the `references/` files reachable at the relative
path `SKILL.md` names, or inline them if the tool does not support file reads.

**Custom agent loops (LangChain, the Agents SDK, your own harness)**: load
`SKILL.md` as a system prompt fragment when the user's request matches the
`description`. Give the agent a shell tool so it can run the script, and a web
fetch tool so it can handle the pages the script cannot read.

**No agent at all**: the scripts are ordinary CLIs that print JSON. Run them and
read the output yourself.

## What the scripts assume

- Python 3.8+ from the standard library, and `curl` on `PATH`.
- Outbound HTTPS. The `vinyl` skill talks to `api.discogs.com` (public, no key,
  25 requests/minute for anonymous callers) and optionally to a shop URL you
  pass it.
- No state, no config files, no credentials. Each run is independent.

Paths inside `SKILL.md` are written relative to the skill directory, with
`${CLAUDE_PLUGIN_ROOT}` offered as a convenience for Claude Code's plugin
loader. Any agent can ignore that variable and use the relative path.

## Porting notes

The `vinyl` skill's judgement lives in `references/pressing-quality.md`, not in
the script. If you want to adapt it — different plant reputations, a different
regional retail context — edit that file and leave the script alone. The script
only fetches and normalises; it deliberately makes no quality calls of its own,
because those are the part a model should reason about with the user in front of
it.
