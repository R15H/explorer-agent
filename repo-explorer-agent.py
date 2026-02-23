#!/usr/bin/env python3
"""
repo-explorer-agent.py — Autonomous Repository Analysis Agent

Drives Claude Code in non-interactive mode to systematically analyze
open-source repositories. Uses the CLAUDE.md and PROMPTS.md methodology
to produce a complete .claude-study/ knowledge base.

Usage:
    python3 repo-explorer-agent.py [options]

    Run from the root of a cloned repository that contains CLAUDE.md.

Requirements:
    - Claude Code installed: npm install -g @anthropic-ai/claude-code
    - Authenticated with Claude (claude login)
    - CLAUDE.md in the repository root
    - Python 3.8+
"""

import argparse
import json
import os
import subprocess
import sys
import time
import textwrap
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

STUDY_DIR = ".claude-study"
STATE_DIR = f"{STUDY_DIR}/.agent-state"
STATE_FILE = f"{STATE_DIR}/state.json"
LOG_FILE = f"{STATE_DIR}/agent.log"

# How many agentic turns Claude Code is allowed per prompt
DEFAULT_MAX_TURNS = 25

# Pause between prompts (seconds) — be kind to rate limits
PAUSE_BETWEEN_PROMPTS = 3

# Model to use
DEFAULT_MODEL = "opus"

# Tools allowed during analysis (read-only + git)
ANALYSIS_TOOLS = "Read,Grep,Glob,Bash(find *),Bash(wc *),Bash(head *),Bash(tail *),Bash(cat *),Bash(ls *),Bash(git *),Bash(tree *),Bash(file *),Bash(stat *),Bash(du *),Bash(sort *),Bash(uniq *),Bash(awk *),Bash(sed *),Bash(grep *),Bash(mkdir *),Write"


# ──────────────────────────────────────────────────────────────────────
# State Management
# ──────────────────────────────────────────────────────────────────────

@dataclass
class PhaseState:
    """Tracks completion state of a single phase."""
    name: str
    status: str = "pending"  # pending | running | done | skipped
    steps_completed: list = field(default_factory=list)
    steps_total: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    session_id: Optional[str] = None
    notes: str = ""


@dataclass
class AgentState:
    """Full agent state, persisted to disk between runs."""
    repo_path: str = ""
    repo_name: str = ""
    started_at: str = ""
    last_run_at: str = ""
    current_phase: str = "survey"
    phases: dict = field(default_factory=dict)
    discovered_subsystems: list = field(default_factory=list)
    discovered_source_dirs: list = field(default_factory=list)
    total_prompts_sent: int = 0
    total_time_seconds: float = 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, data: str) -> "AgentState":
        d = json.loads(data)
        phases_raw = d.pop("phases", {})
        state = cls(**d)
        state.phases = {
            k: PhaseState(**v) for k, v in phases_raw.items()
        }
        return state

    def save(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        Path(STATE_FILE).write_text(self.to_json())

    @classmethod
    def load(cls) -> "AgentState":
        if Path(STATE_FILE).exists():
            return cls.from_json(Path(STATE_FILE).read_text())
        return cls()


# ──────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────

class Logger:
    def __init__(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        self.log_path = Path(LOG_FILE)

    def log(self, level: str, msg: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] {msg}"
        print(line)
        with open(self.log_path, "a") as f:
            f.write(line + "\n")

    def info(self, msg): self.log("INFO", msg)
    def warn(self, msg): self.log("WARN", msg)
    def error(self, msg): self.log("ERROR", msg)
    def phase(self, msg): self.log("PHASE", f"{'='*60}\n{msg}\n{'='*60}")


logger = Logger()


# ──────────────────────────────────────────────────────────────────────
# Claude Code Interface
# ──────────────────────────────────────────────────────────────────────

def run_claude(
    prompt: str,
    max_turns: int = DEFAULT_MAX_TURNS,
    model: str = DEFAULT_MODEL,
    continue_session: bool = False,
    session_id: Optional[str] = None,
    append_system: Optional[str] = None,
    timeout_minutes: int = 15,
) -> dict:
    """
    Run Claude Code in non-interactive mode.

    Returns dict with:
        - success: bool
        - output: str (text response)
        - session_id: str (for session continuity)
        - duration: float (seconds)
    """
    cmd = ["claude", "-p", prompt]
    cmd += ["--output-format", "json"]
    cmd += ["--max-turns", str(max_turns)]
    cmd += ["--model", model]
    cmd += ["--allowedTools", ANALYSIS_TOOLS]

    if continue_session and not session_id:
        cmd += ["--continue"]
    elif session_id:
        cmd += ["--resume", session_id]

    if append_system:
        cmd += ["--append-system-prompt", append_system]

    logger.info(f"Running prompt ({len(prompt)} chars, max_turns={max_turns})...")
    logger.info(f"  First 120 chars: {prompt[:120]}...")

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_minutes * 60,
            cwd=os.getcwd(),
        )
        duration = time.time() - start

        if result.returncode != 0:
            logger.error(f"Claude Code returned {result.returncode}")
            logger.error(f"  stderr: {result.stderr[:500]}")
            return {
                "success": False,
                "output": result.stderr,
                "session_id": None,
                "duration": duration,
            }

        # Parse JSON output
        output_text = result.stdout.strip()
        sid = None

        try:
            data = json.loads(output_text)
            # JSON format returns: { "result": "...", "session_id": "...", ... }
            output_text = data.get("result", output_text)
            sid = data.get("session_id")
        except json.JSONDecodeError:
            # Fall back to raw text if not valid JSON
            pass

        logger.info(f"  Completed in {duration:.1f}s, output length: {len(output_text)}")
        return {
            "success": True,
            "output": output_text,
            "session_id": sid,
            "duration": duration,
        }

    except subprocess.TimeoutExpired:
        duration = time.time() - start
        logger.error(f"  Timed out after {timeout_minutes} minutes")
        return {
            "success": False,
            "output": f"TIMEOUT after {timeout_minutes} minutes",
            "session_id": None,
            "duration": duration,
        }
    except FileNotFoundError:
        logger.error("Claude Code not found. Install with: npm install -g @anthropic-ai/claude-code")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────
# Phase Definitions
# ──────────────────────────────────────────────────────────────────────

# Each phase is a list of (step_name, prompt) tuples.
# Prompts can use {repo_name} and {subsystems} template variables.

PHASE_SURVEY = [
    ("scaffold", textwrap.dedent("""\
        Create the .claude-study/ directory structure as defined in CLAUDE.md:
        - .claude-study/README.md (index file, start with a header and description)
        - .claude-study/architecture/
        - .claude-study/deep-dives/
        - .claude-study/nuggets/
        - .claude-study/decisions/
        - .claude-study/contribution-notes/
        Create the directories and empty index files. This is the foundation
        for everything we'll produce.
    """)),
    ("read_top_level", textwrap.dedent("""\
        Read and analyze the top-level directory structure, README.md,
        CONTRIBUTING.md (if it exists), LICENSE, and the build system files
        (Makefile, CMakeLists.txt, configure, meson.build, Cargo.toml,
        package.json — whatever exists).

        From this, determine:
        1. What this project is and what it does
        2. The primary language(s) and build system
        3. The test framework and how to run tests
        4. The CI/CD setup

        Write the results to .claude-study/build-and-test.md
    """)),
    ("find_entry_points", textwrap.dedent("""\
        Find the main entry point(s) of this project. Look for main(),
        the event loop initialization, the top-level driver, or the
        primary server startup code.

        Read these files and understand the startup sequence.

        Then map ALL top-level modules and directories. For each one,
        determine its responsibility based on reading its header files
        or top-level source files. Don't guess — actually read the code.

        Write a comprehensive module map to .claude-study/architecture/module-map.md
        Include file paths and one-paragraph descriptions for each module.
    """)),
    ("write_overview", textwrap.dedent("""\
        Based on everything you've read so far (the README, build files,
        entry points, and module map), write a comprehensive architectural
        overview of this project.

        Cover:
        - What the system does (one paragraph, plain language)
        - High-level architecture (what are the major components and how do
          they interact)
        - The key data structures that hold everything together
        - The main execution flow (what happens when the system starts,
          receives a request, processes it, and responds)
        - Design philosophy (single-threaded vs multi-threaded, event-driven
          vs blocking, etc.)

        Use Mermaid diagrams where they add clarity.
        Write to .claude-study/architecture/overview.md

        Also create a .claude-study/glossary.md with project-specific
        terminology you've encountered.
    """)),
    ("git_archaeology_overview", textwrap.dedent("""\
        Do a quick archaeological survey of the git history:

        1. Run: git log --oneline -30 (last 30 commits — what's active?)
        2. Run: git shortlog -sn --no-merges | head -20 (top contributors)
        3. Run: git log --oneline --since="6 months ago" --diff-filter=A -- "*.c" "*.cc" "*.cpp" "*.h" "*.py" "*.rs" "*.go" "*.java" | head -20
           (recently added source files)
        4. Check if there are any RFCs, design docs, or architecture docs
           in the repo (look for docs/, doc/, design/, rfc/, proposals/)

        Summarize findings. Note the most active areas, key contributors,
        and any design documents found.
        Append this to .claude-study/architecture/overview.md as a
        "Repository Health & Activity" section.
    """)),
    ("update_index", textwrap.dedent("""\
        Update .claude-study/README.md to be a proper index of everything
        we've produced so far. List each document with a brief description
        and relative link. This is the table of contents for the whole
        study.
    """)),
]


PHASE_DEEP_DIVE_TEMPLATE = [
    ("interfaces", textwrap.dedent("""\
        Deep dive: {subsystem}

        STEP 1 — INTERFACES
        Read all the header files / public interfaces for the {subsystem}
        subsystem. Identify:
        - The public API (functions, types, constants)
        - The data structures and their fields
        - Any documented invariants or contracts

        Start writing to .claude-study/deep-dives/{subsystem_slug}.md
        Begin with the interface analysis.
    """)),
    ("implementation", textwrap.dedent("""\
        Deep dive: {subsystem} (continued)

        STEP 2 — IMPLEMENTATION
        Now read the core implementation files for {subsystem}. Trace the
        primary execution paths. Focus on:
        - The main algorithms and their complexity
        - How errors are handled and propagated
        - Memory management (who allocates, who frees)
        - Any performance-critical hot paths

        Continue writing to .claude-study/deep-dives/{subsystem_slug}.md
    """)),
    ("git_history", textwrap.dedent("""\
        Deep dive: {subsystem} (continued)

        STEP 3 — HISTORY & RATIONALE
        Use git log and git blame on the key files of {subsystem}.
        - Find the commits that introduced major features or changes
        - Read the commit messages for design rationale
        - Note any referenced issues or PR numbers
        - Look for reverted commits (failed approaches)

        Add a "History & Design Rationale" section to
        .claude-study/deep-dives/{subsystem_slug}.md
    """)),
    ("nuggets_in_subsystem", textwrap.dedent("""\
        Deep dive: {subsystem} (continued)

        STEP 4 — NUGGET EXTRACTION
        Now that you understand {subsystem} deeply, find 2-4 code nuggets
        in this subsystem. Look for:
        - Elegant algorithms or data structures
        - Clever optimizations
        - Exemplary error handling
        - Beautiful abstractions

        Write each nugget as a full document under .claude-study/nuggets/
        following the nugget format from CLAUDE.md.
        Update .claude-study/nuggets/index.md with the new entries.
    """)),
]


PHASE_BROAD_NUGGETS = [
    ("sweep_core", textwrap.dedent("""\
        Systematic nugget sweep — CORE FILES

        Scan the most important source files in this project (the ones
        at the heart of the system — the entry point, the main event
        loop, the core data structures, the primary algorithms).

        Find 5-8 code nuggets across categories:
        - Algorithm implementations
        - Performance optimizations
        - Defensive programming patterns
        - API design choices
        - Bit manipulation or mathematical tricks

        Write each as a full nugget document under .claude-study/nuggets/
        Update .claude-study/nuggets/index.md
    """)),
    ("sweep_utilities", textwrap.dedent("""\
        Systematic nugget sweep — UTILITIES & INFRASTRUCTURE

        Now scan the utility/helper code — string handling, memory
        allocators, logging, configuration parsing, testing utilities,
        build system tricks.

        These often contain the most transferable patterns because
        they're not domain-specific.

        Find 3-5 nuggets. Full nugget documents.
        Update .claude-study/nuggets/index.md
    """)),
    ("sweep_tests", textwrap.dedent("""\
        Systematic nugget sweep — TEST PATTERNS

        Examine the test suite. Look for:
        - Unusually thorough test patterns
        - Creative use of mocking, fuzzing, or property-based testing
        - Performance benchmarks embedded in tests
        - Regression tests that tell a story about past bugs

        Find 2-3 nuggets from the tests.
        Update .claude-study/nuggets/index.md
    """)),
]


PHASE_DECISIONS = [
    ("major_decisions", textwrap.dedent("""\
        Design Decision Archaeology

        Based on everything you've learned about this codebase, identify
        the 3-5 most important architectural decisions the authors made.
        These are the choices that shaped everything else.

        For each decision, investigate:
        - What was chosen and what were the alternatives
        - Use git blame, git log, commit messages, and code comments
          to find evidence of WHY
        - Note any PR/issue numbers referenced
        - Explain the consequences — what does this decision enable
          or prevent?

        Write each as a decision document under .claude-study/decisions/
        following the template in CLAUDE.md.
    """)),
]


PHASE_CONTRIBUTIONS = [
    ("find_opportunities", textwrap.dedent("""\
        Contribution Opportunity Scan

        Search this codebase for ways someone could contribute:

        1. Grep for TODO, FIXME, HACK, XXX, WORKAROUND comments.
           Cross-reference with git blame — how old are they?
        2. Look at the test suite: which modules have no tests or
           obviously thin coverage?
        3. Check for functions with weak error handling (missing NULL
           checks, unchecked return values, etc.)
        4. Find documentation that's outdated or contradicts the code
        5. Look at git log for areas with many recent bug-fix commits
           (fragile code)

        Categorize findings by difficulty: easy, medium, hard.
        Write to .claude-study/contribution-notes/good-first-issues.md
        and .claude-study/contribution-notes/potential-improvements.md
    """)),
    ("style_analysis", textwrap.dedent("""\
        Coding Style & Conventions Analysis

        Analyze this project's coding conventions so a contributor
        can match the style. Cover:
        - Naming conventions (functions, variables, types, macros, files)
        - Formatting (indentation, braces, line length)
        - Comment style and philosophy
        - Error handling patterns
        - How new modules/features are typically structured
        - Header file organization and include patterns

        Write to .claude-study/contribution-notes/style-guide.md
    """)),
]


PHASE_FINAL = [
    ("final_index", textwrap.dedent("""\
        Final index update.

        Read through everything in .claude-study/ and rewrite the
        .claude-study/README.md to be a comprehensive, well-organized
        index of the entire study.

        Group documents by category, add brief descriptions, and
        include a "Recommended Reading Order" section for someone
        who wants to understand this codebase from scratch.

        Also add a "Key Insights" section at the top with the 5-10
        most important things we learned about this codebase.
    """)),
]


# ──────────────────────────────────────────────────────────────────────
# Phase Orchestration
# ──────────────────────────────────────────────────────────────────────

PHASE_ORDER = [
    "survey",
    "deep_dives",
    "broad_nuggets",
    "decisions",
    "contributions",
    "final",
]


def discover_subsystems(state: AgentState) -> list[str]:
    """
    After the survey phase, ask Claude to identify key subsystems
    worth deep-diving into.
    """
    logger.info("Discovering subsystems for deep dives...")

    prompt = textwrap.dedent("""\
        Based on the module map and architecture overview you've written
        in .claude-study/, identify the 3-5 most important and interesting
        subsystems in this codebase for deep-dive analysis.

        Choose subsystems that are:
        - Central to the system's purpose
        - Architecturally interesting or novel
        - Complex enough to warrant detailed study
        - Likely to contain good code nuggets

        Respond with ONLY a JSON array of objects, no other text:
        [
            {"name": "Human-readable name", "slug": "kebab-case-slug", "path": "src/relevant/dir", "why": "One sentence reason"}
        ]
    """)

    result = run_claude(prompt, max_turns=10, continue_session=True)
    if not result["success"]:
        logger.warn("Failed to discover subsystems, using fallback")
        return []

    # Extract JSON from response
    output = result["output"]
    try:
        # Try to find JSON array in the output
        start = output.index("[")
        end = output.rindex("]") + 1
        subsystems = json.loads(output[start:end])
        logger.info(f"Discovered {len(subsystems)} subsystems:")
        for s in subsystems:
            logger.info(f"  - {s['name']} ({s['path']}): {s['why']}")
        return subsystems
    except (ValueError, json.JSONDecodeError) as e:
        logger.warn(f"Could not parse subsystem list: {e}")
        logger.warn(f"Raw output: {output[:500]}")
        return []


def run_phase_steps(
    phase_name: str,
    steps: list[tuple[str, str]],
    state: AgentState,
    model: str,
    max_turns: int,
    template_vars: Optional[dict] = None,
    pause: int = PAUSE_BETWEEN_PROMPTS,
):
    """Execute a sequence of prompt steps for a phase."""
    phase = state.phases.setdefault(
        phase_name,
        PhaseState(name=phase_name, steps_total=len(steps))
    )
    phase.status = "running"
    phase.started_at = phase.started_at or datetime.now().isoformat()
    phase.steps_total = len(steps)
    state.save()

    for step_name, prompt_template in steps:
        if step_name in phase.steps_completed:
            logger.info(f"  Skipping already-completed step: {step_name}")
            continue

        # Apply template variables
        prompt = prompt_template
        if template_vars:
            for k, v in template_vars.items():
                prompt = prompt.replace(f"{{{k}}}", str(v))

        logger.info(f"  Step: {step_name}")
        result = run_claude(
            prompt,
            max_turns=max_turns,
            model=model,
            continue_session=True,
        )
        state.total_prompts_sent += 1
        state.total_time_seconds += result["duration"]

        if result["success"]:
            phase.steps_completed.append(step_name)
            if result["session_id"]:
                phase.session_id = result["session_id"]
        else:
            logger.error(f"  Step '{step_name}' failed — continuing to next step")
            phase.notes += f"\nFailed step: {step_name}: {result['output'][:200]}"

        state.save()
        time.sleep(pause)

    phase.status = "done"
    phase.finished_at = datetime.now().isoformat()
    state.save()


def run_agent(
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    phases_to_run: Optional[list[str]] = None,
    max_deep_dives: int = 4,
    skip_existing: bool = True,
    pause: int = PAUSE_BETWEEN_PROMPTS,
):
    """Main agent loop."""
    state = AgentState.load()

    # Initialize state for a fresh run
    if not state.repo_path:
        state.repo_path = os.getcwd()
        state.repo_name = os.path.basename(os.getcwd())
        state.started_at = datetime.now().isoformat()

    state.last_run_at = datetime.now().isoformat()
    state.save()

    phases = phases_to_run or PHASE_ORDER

    logger.phase(f"REPOSITORY EXPLORER AGENT — {state.repo_name}")
    logger.info(f"Repo: {state.repo_path}")
    logger.info(f"Model: {model}")
    logger.info(f"Phases: {', '.join(phases)}")
    logger.info(f"Max turns per prompt: {max_turns}")
    logger.info(f"Previous prompts sent: {state.total_prompts_sent}")

    # Check prerequisites
    if not Path("CLAUDE.md").exists():
        logger.error("CLAUDE.md not found in repo root. Copy it here first.")
        sys.exit(1)

    for phase_name in phases:
        # Skip completed phases
        existing = state.phases.get(phase_name)
        if skip_existing and existing and existing.status == "done":
            logger.info(f"Skipping completed phase: {phase_name}")
            continue

        logger.phase(f"PHASE: {phase_name}")

        if phase_name == "survey":
            run_phase_steps("survey", PHASE_SURVEY, state, model, max_turns, pause=pause)

        elif phase_name == "deep_dives":
            # Discover subsystems if not already done
            if not state.discovered_subsystems:
                subsystems = discover_subsystems(state)
                state.discovered_subsystems = subsystems
                state.save()

            subsystems = state.discovered_subsystems[:max_deep_dives]

            if not subsystems:
                logger.warn("No subsystems discovered — skipping deep dives")
                state.phases["deep_dives"] = PhaseState(
                    name="deep_dives", status="skipped",
                    notes="No subsystems discovered"
                )
                state.save()
                continue

            for i, sub in enumerate(subsystems):
                sub_name = sub["name"]
                sub_slug = sub["slug"]
                sub_phase = f"deep_dive_{sub_slug}"

                logger.info(f"Deep dive {i+1}/{len(subsystems)}: {sub_name}")

                template_vars = {
                    "subsystem": sub_name,
                    "subsystem_slug": sub_slug,
                    "subsystem_path": sub.get("path", ""),
                }

                run_phase_steps(
                    sub_phase,
                    PHASE_DEEP_DIVE_TEMPLATE,
                    state,
                    model,
                    max_turns,
                    template_vars=template_vars,
                    pause=pause,
                )

            # Mark the umbrella phase as done
            state.phases["deep_dives"] = PhaseState(
                name="deep_dives", status="done",
                finished_at=datetime.now().isoformat(),
                notes=f"Completed {len(subsystems)} deep dives"
            )
            state.save()

        elif phase_name == "broad_nuggets":
            run_phase_steps("broad_nuggets", PHASE_BROAD_NUGGETS, state, model, max_turns, pause=pause)

        elif phase_name == "decisions":
            run_phase_steps("decisions", PHASE_DECISIONS, state, model, max_turns, pause=pause)

        elif phase_name == "contributions":
            run_phase_steps("contributions", PHASE_CONTRIBUTIONS, state, model, max_turns, pause=pause)

        elif phase_name == "final":
            run_phase_steps("final", PHASE_FINAL, state, model, max_turns, pause=pause)

        else:
            logger.warn(f"Unknown phase: {phase_name}")

    # Summary
    logger.phase("AGENT COMPLETE")
    logger.info(f"Total prompts sent: {state.total_prompts_sent}")
    logger.info(f"Total time: {state.total_time_seconds/60:.1f} minutes")
    logger.info(f"Artifacts: .claude-study/")

    # Print what was produced
    if Path(STUDY_DIR).exists():
        result = subprocess.run(
            ["find", STUDY_DIR, "-name", "*.md", "-not", "-path", "*/.agent-state/*"],
            capture_output=True, text=True
        )
        files = sorted(result.stdout.strip().split("\n"))
        logger.info(f"Documents produced ({len(files)}):")
        for f in files:
            if f:
                logger.info(f"  {f}")


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Repository Analysis Agent — drives Claude Code "
                    "to systematically study open-source codebases.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              # Full analysis with defaults
              python3 repo-explorer-agent.py

              # Use Opus, deeper analysis
              python3 repo-explorer-agent.py --model opus --max-turns 30

              # Only run survey and nugget phases
              python3 repo-explorer-agent.py --phases survey broad_nuggets

              # Resume a previously interrupted run
              python3 repo-explorer-agent.py --resume

              # Start fresh, ignoring previous state
              python3 repo-explorer-agent.py --fresh

              # Limit deep dives to 2 subsystems
              python3 repo-explorer-agent.py --max-deep-dives 2

            Available phases:
              survey         — Initial repo survey (architecture, modules, build)
              deep_dives     — Deep exploration of key subsystems
              broad_nuggets  — Systematic code nugget extraction
              decisions      — Design decision archaeology
              contributions  — Contribution opportunity scanning
              final          — Final index and summary generation
        """)
    )

    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        choices=["opus", "sonnet", "haiku"],
        help="Claude model to use (default: opus)"
    )
    parser.add_argument(
        "--max-turns", type=int, default=DEFAULT_MAX_TURNS,
        help=f"Max agentic turns per prompt (default: {DEFAULT_MAX_TURNS})"
    )
    parser.add_argument(
        "--phases", nargs="+", choices=PHASE_ORDER, default=None,
        help="Run only specific phases (default: all)"
    )
    parser.add_argument(
        "--max-deep-dives", type=int, default=4,
        help="Maximum number of subsystem deep dives (default: 4)"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from last saved state, skipping completed phases/steps"
    )
    parser.add_argument(
        "--fresh", action="store_true",
        help="Start fresh, deleting any previous state"
    )
    parser.add_argument(
        "--pause", type=int, default=PAUSE_BETWEEN_PROMPTS,
        help=f"Seconds to pause between prompts (default: {PAUSE_BETWEEN_PROMPTS})"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show current agent state and exit"
    )

    args = parser.parse_args()

    # Status mode
    if args.status:
        state = AgentState.load()
        if not state.repo_path:
            print("No previous run found.")
            return
        print(f"Repository: {state.repo_name}")
        print(f"Started: {state.started_at}")
        print(f"Last run: {state.last_run_at}")
        print(f"Prompts sent: {state.total_prompts_sent}")
        print(f"Total time: {state.total_time_seconds/60:.1f} min")
        print(f"Current phase: {state.current_phase}")
        print(f"\nPhases:")
        for name, phase in state.phases.items():
            completed = len(phase.steps_completed)
            total = phase.steps_total
            print(f"  {name}: {phase.status} ({completed}/{total} steps)")
        if state.discovered_subsystems:
            print(f"\nDiscovered subsystems:")
            for s in state.discovered_subsystems:
                print(f"  - {s['name']} ({s.get('path', '?')})")
        return

    # Fresh start
    if args.fresh:
        import shutil
        if Path(STATE_DIR).exists():
            shutil.rmtree(STATE_DIR)
            logger.info("Cleared previous state.")

    run_agent(
        pause=args.pause,
        model=args.model,
        max_turns=args.max_turns,
        phases_to_run=args.phases,
        max_deep_dives=args.max_deep_dives,
        skip_existing=args.resume or (not args.fresh),
    )


if __name__ == "__main__":
    main()
