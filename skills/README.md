# Account Manager Agent Skills

This folder holds the [Agent Skills](https://agentskills.io/specification) for
working on Account Manager with an AI coding agent such as Claude Code. This
README is written for people.

A skill is a folder of written know-how that an agent loads only when a task
needs it. Each one contains a `SKILL.md` file, and sometimes `references/` and
`scripts/` folders. These skills cover how this repository is built, tested
and committed. They are developer tooling, like the `Makefile` and
`.pre-commit-config.yaml`; no Account Manager code loads them at runtime.

They are modeled on the skills of smarter-sh/smarter (`../smarter/skills/` in
a side-by-side checkout), scaled down to this much smaller project. Where these
skills have no answer, the Smarter skills usually do.

## What's here

Start with `am-development`. It sets out the rules that apply to every change,
and its table says which narrower skill to load for each kind of task.

| Skill                   | Use it when                                                           |
| ----------------------- | --------------------------------------------------------------------- |
| `am-development`        | You're making any change. Start here.                                 |
| `am-python-testing`     | You're writing or running unit tests, or raising coverage.            |
| `am-docker-environment` | Code must run in the containers (tests, migrations, `manage.py`).     |
| `am-migrations`         | A model changes and needs a migration.                                |
| `am-code-quality`       | You're about to finish a change and need to run the pre-commit hooks. |
| `am-git-commits`        | You've been asked to write a commit message.                          |
| `am-pull-requests`      | You've been asked to create or describe a pull request.               |
| `am-ci-failures`        | A GitHub Actions run or job failed, or the user gives you a run url.  |

### Layout of a skill

```text
am-ci-failures/
├── SKILL.md            # required: YAML frontmatter (name, description) + instructions
├── references/         # optional: longer material the agent reads only if needed
└── scripts/            # optional: helper scripts the agent (or you) can run
    └── fetch-run-logs.sh
```

The frontmatter `description` matters most. An agent sees only each skill's
`name` and `description` until it decides a skill is relevant; only then does
it read the body. A vague description means the skill never gets used; one
that's too broad means it gets loaded, and followed, for unrelated work.

The bundled script is an ordinary shell script that you can run yourself from
the repository root: `am-ci-failures/scripts/fetch-run-logs.sh <run url>`
downloads a failed run's logs and prints its failures.

## Why this folder exists

Much of what you need to know about this repository isn't obvious from the
code. For example:

- The containers run a copy of the code baked into the image, so host edits
  don't reach them until you rebuild or copy them in.
- `make docker-init` drops the local database.
- `make run` never returns.
- Smarter's `smarter-mariadb` container also wants port 3306.
- Migrations run against production data, so they are append-only.
- Commit messages drive semantic-release, and follow a particular format.

Written down here, that knowledge is reviewed in pull requests and shared by
everyone who works on the repository, rather than relearned by each new session
or contributor.

## When to add or change a skill

Add to a skill when you've explained the same thing to an agent more than once,
when a mistake is costly or hard to undo, or when checking a change takes a
fragile series of steps (put those in a script under `scripts/`).

Don't add a skill for things the code, the linters or CI already enforce, for
one-off facts (use a comment or a docstring), for personal preferences (use
`~/.claude/`), or for anything private. **This repository is public**: never
put API keys, tokens, account ids, private hostnames or customer data in a
skill, an example or a script.

Prefer editing an existing skill to adding one. If you add one, add it to the
table above and to the index in `am-development/SKILL.md`.

### Writing guidelines

- Name the folder `am-<topic>`, and set the frontmatter `name` to the same
  value.
- Write the `description` as "Use when ...", naming the concrete situations
  that should trigger it, under 1,024 characters.
- Keep `SKILL.md` short and specific, and explain _why_ a rule exists.
- Point to real files in the repository rather than copying their code.
- Don't add a `README.md` inside a skill's folder.

## What uses these skills

Claude Code looks for project skills in `.claude/skills/<name>/SKILL.md`. This
repository connects that location to this folder with a committed symlink,
`.claude/skills -> ../skills`, created with:

```bash
# from the repository root
mkdir -p .claude
ln -s ../skills .claude/skills
```

Claude Code lists each skill's name and description, loads a skill's body when
a task matches, and also lets you invoke one directly, e.g.
`/am-git-commits`. If the symlink breaks (for example on a Windows checkout
without symlink support), Claude Code silently stops seeing the skills. Other
agents that support Agent Skills read `SKILL.md` folders from their own
configuration locations; agents that don't can be told to read
`skills/am-development/SKILL.md` at the start of a session.

## Security considerations

A skill is a set of instructions that an agent follows, often without asking.
**Review a change to this folder with the same care as a change to CI or a
deploy script.**

- **The local environment holds real credentials.** The containers read
  `.env`, which holds working SMTP credentials and whatever AWS
  or Stripe keys a developer adds. `am-python-testing` requires every test to
  mock those services; don't weaken it.
- **Some rules forbid things on purpose.** `am-git-commits` tells the agent
  never to run `git commit`, `git add` or `git push`. Don't remove a rule like
  that unless you mean to give agents that power.
- **Skills can carry prompt injection.** Look for instructions unrelated to a
  skill's purpose, new network calls in scripts, text that tells the agent to
  skip confirmations or hooks, and links it is told to fetch and follow.
- **Stale skills mislead.** When you change something a skill describes (a make
  target, a container name, a path, a base class), update the skill in the
  same pull request.
