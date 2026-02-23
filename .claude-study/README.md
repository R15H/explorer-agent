# LLVM Project — Codebase Study

A comprehensive analysis of the [LLVM Compiler Infrastructure](https://github.com/llvm/llvm-project) project (version 23.0.0git, main branch).

**Generated:** 2026-02-23

---

## Table of Contents

### Architecture
- [**Overview**](architecture/overview.md) — High-level system architecture, design philosophy, and scale of the project
- [**Module Map**](architecture/module-map.md) — Detailed breakdown of every directory in the monorepo and `llvm/` subtree
- [**Data Flow**](architecture/data-flow.md) — How data moves from source code through IR optimization to machine code, including all intermediate representations

### Reference
- [**Build and Test**](build-and-test.md) — How to build LLVM, run tests, and use development tools
- [**Glossary**](glossary.md) — LLVM-specific terminology (IR concepts, pass types, data structures, tools)

### Deep Dives
- [**IR Core**](deep-dives/ir-core.md) — The LLVM Intermediate Representation: Value/User/Use triangle, type system, instruction set, IRBuilder, Verifier, metadata
- [**Pass Manager**](deep-dives/pass-manager.md) — New vs Legacy Pass Manager, analysis caching, invalidation protocol, PassBuilder pipelines
- [**Code Generation**](deep-dives/code-generation.md) — SelectionDAG, GlobalISel, MachineInstr, register allocation, MC layer, TableGen target descriptions

### Code Nuggets
- [**Nuggets Index**](nuggets/index.md) — Catalog of all extracted code nuggets

Individual nuggets:
1. [LLVM Custom RTTI (isa/cast/dyn_cast)](nuggets/pattern/llvm-rtti.md) — Pattern: how LLVM implements fast type checking without C++ RTTI
2. [Use-Def Chain](nuggets/abstraction/use-def-chain.md) — Abstraction: the intrusive linked list connecting SSA definitions to their uses
3. [BumpPtrAllocator](nuggets/optimization/bump-ptr-allocator.md) — Optimization: arena allocation for compiler workloads
4. [SmallVector](nuggets/optimization/small-vector.md) — Optimization: inline storage to avoid heap allocation for small collections
5. [Error (Mandatory Checking)](nuggets/defensive/error-must-check.md) — Defensive: enforced error handling via destructor checks
6. [ilist (Intrusive List)](nuggets/abstraction/ilist.md) — Abstraction: zero-allocation doubly-linked list for IR nodes

### Design Decisions
- [**Opaque Pointers**](decisions/opaque-pointers.md) — Why LLVM removed pointee types from pointers (typed `i32*` → opaque `ptr`)
- [**New Pass Manager**](decisions/new-pass-manager.md) — Why LLVM replaced the legacy pass manager with a template-based design
- [**Custom RTTI**](decisions/custom-rtti.md) — Why LLVM uses `isa<>/cast<>/dyn_cast<>` instead of C++ `dynamic_cast`

### Contribution Notes
- [**Good First Issues**](contribution-notes/good-first-issues.md) — Accessible entry points for new contributors
- [**Potential Improvements**](contribution-notes/potential-improvements.md) — Larger feature and refactoring ideas
- [**Bug Hypotheses**](contribution-notes/bug-hypotheses.md) — Fragile areas and suspected issues found during study

---

## Quick Stats

| Metric | Value |
|--------|-------|
| LLVM version | 23.0.0git |
| Primary language | C++17 |
| Build system | CMake 3.20+ |
| C++ files in `llvm/` | ~7,700 |
| Lines of C++ in `llvm/lib/` | ~209,000 |
| Target backends | 30+ |
| Analysis passes | 127 |
| Scalar optimization passes | 82 |
| CodeGen files | 258 |
| Subprojects in monorepo | 25+ |

---

## How to Use This Study

- **New to LLVM?** Start with [Architecture Overview](architecture/overview.md), then [Glossary](glossary.md), then [Build and Test](build-and-test.md).
- **Want to understand the IR?** Read [IR Core deep dive](deep-dives/ir-core.md) and the [Use-Def Chain nugget](nuggets/abstraction/use-def-chain.md).
- **Want to write an optimization pass?** Read [Pass Manager deep dive](deep-dives/pass-manager.md) and look at `lib/Transforms/Scalar/` examples.
- **Want to understand code generation?** Read [Code Generation deep dive](deep-dives/code-generation.md) and the [Data Flow](architecture/data-flow.md) document.
- **Want to contribute?** Start with [Good First Issues](contribution-notes/good-first-issues.md).
