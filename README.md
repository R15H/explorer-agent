# Repository Explorer Kit

An autonomous agent that uses Claude Code to systematically analyze open-source repositories — producing architecture docs, code nuggets, design decision archaeology, and contribution guides.

## What's in the Kit

| File | Purpose |
|---|---|
| `CLAUDE.md` | Drop into any repo root. Defines workflows, artifact structure, and operating principles for Claude Code sessions. |
| `PROMPTS.md` | Ready-to-paste prompts for manual Claude Code sessions organized in 5 phases. |
| `repo-explorer-agent.py` | Autonomous agent that drives Claude Code non-interactively through all phases. |

## Quick Start

### 1. Install Prerequisites

```bash
# Claude Code
npm install -g @anthropic-ai/claude-code

# Authenticate
claude login

# Python 3.8+ (should already be installed)
python3 --version
```

### 2. Clone a Target Repo

```bash
git clone https://github.com/redis/redis.git
cd redis
```

### 3. Copy the Kit Files

```bash
cp /path/to/CLAUDE.md .
cp /path/to/repo-explorer-agent.py .
```

### 4. Run the Agent

```bash
# Full autonomous analysis (all phases)
python3 repo-explorer-agent.py

# Faster pass with Sonnet
python3 repo-explorer-agent.py --model sonnet

# Only survey + nuggets
python3 repo-explorer-agent.py --phases survey broad_nuggets

# Deep analysis with Opus, more turns
python3 repo-explorer-agent.py --model opus --max-turns 30

# Check progress
python3 repo-explorer-agent.py --status

# Resume after interruption
python3 repo-explorer-agent.py --resume
```

## What the Agent Produces

All artifacts go under `.claude-study/` in the repo:

```
.claude-study/
├── README.md                        ← Master index with reading order
├── architecture/
│   ├── overview.md                  ← System architecture + Mermaid diagrams
│   └── module-map.md                ← Every module with responsibilities
├── deep-dives/
│   ├── <subsystem-1>.md             ← Detailed subsystem explorations
│   ├── <subsystem-2>.md
│   └── ...
├── nuggets/
│   ├── index.md                     ← Catalog of all extracted nuggets
│   └── <category>/
│       └── <name>.md                ← Individual code nuggets with context
├── decisions/
│   └── <topic>.md                   ← Reverse-engineered design decisions
├── glossary.md                      ← Project-specific terminology
├── build-and-test.md                ← How to build, test, run
└── contribution-notes/
    ├── good-first-issues.md         ← Easy contribution opportunities
    ├── potential-improvements.md    ← Larger feature/refactor ideas
    └── style-guide.md              ← Coding conventions for contributors
```

## The Six Phases

| # | Phase | What It Does | Typical Time |
|---|---|---|---|
| 1 | **survey** | Reads top-level files, maps modules, writes architecture overview, examines git history | 10-20 min |
| 2 | **deep_dives** | Auto-discovers 3-5 key subsystems, then deep-dives each one (interfaces → implementation → git history → nuggets) | 30-60 min |
| 3 | **broad_nuggets** | Sweeps core files, utilities, and tests for noteworthy code patterns | 15-25 min |
| 4 | **decisions** | Reverse-engineers the 3-5 most important architectural decisions using git archaeology | 10-20 min |
| 5 | **contributions** | Finds TODOs/FIXMEs, test gaps, weak error handling, style conventions | 10-15 min |
| 6 | **final** | Rewrites the master index with reading order, key insights summary | 5-10 min |

## State & Resumability

The agent tracks state in `.claude-study/.agent-state/`:

- **Automatic resume**: If interrupted, re-running the agent skips completed steps
- **`--status`**: Shows what's been done and what remains
- **`--fresh`**: Starts over from scratch
- **`--resume`**: Explicitly opts into resume mode
- **`--phases`**: Run only specific phases

## Manual Mode

If you prefer interactive Claude Code sessions, use the prompts in `PROMPTS.md`. Start a session:

```bash
cd /path/to/repo  # must contain CLAUDE.md
claude
```

Then paste prompts from the Phase 1-5 sections. Claude Code reads `CLAUDE.md` automatically and follows the workflows defined there.

## Tips

- **Start with `--model sonnet`** for faster, cheaper surveys. Switch to `--model opus` for deep dives and nugget extraction where quality matters most.
- **Limit deep dives** with `--max-deep-dives 2` on very large repos to keep the first run manageable.
- **Commit `.claude-study/` to a personal branch** so the knowledge persists and grows over time.
- **Run specific phases** as you need them: `--phases contributions` before submitting a PR, `--phases broad_nuggets` when you want to learn patterns.
- **Increase `--max-turns`** to 30-40 for complex repos (LLVM, V8) where Claude needs more steps to trace through deep call graphs.

## Tested With

Designed for large C/C++/systems codebases like:
- **Redis** — in-memory data store
- **LLVM** — compiler infrastructure
- **V8** — JavaScript engine
- **SQLite** — embedded database
- **Linux kernel** subsystems
- **Jemalloc** — memory allocator

Works with any language or project that Claude Code can read.
