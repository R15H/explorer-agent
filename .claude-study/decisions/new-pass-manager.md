# Decision: New Pass Manager

**Area:** Pass infrastructure
**Evidence:** `include/llvm/IR/PassManager.h`, `lib/Passes/PassBuilder.cpp`, [LLVM Dev Meeting talks](https://llvm.org/devmtg/)

## The Decision

Replace the Legacy Pass Manager (LPM) with a new template-based Pass Manager (NPM) that uses explicit analysis results, RAII-based invalidation, and a cleaner C++ design.

## The Alternatives

1. **Keep the Legacy Pass Manager** — virtual-inheritance-based, `getAnalysis<T>()` for dependency resolution, static dependency declaration.
2. **New Pass Manager** — template-based, explicit `AnalysisManager::getResult<T>()`, `PreservedAnalyses` invalidation protocol.
3. **Incremental refactoring of LPM** — not practical due to fundamental design issues.

## Why This Way

The Legacy Pass Manager had several problems:

1. **Implicit analysis dependencies.** Passes declared dependencies in `getAnalysisUsage()` but obtained results via `getAnalysis<T>()`. The manager had to run all declared analyses upfront, even if the pass only used some of them conditionally.

2. **Unclear invalidation.** The LPM's invalidation was based on pass types (ModulePass vs FunctionPass) rather than explicit preservation. A module pass would invalidate all function analyses, even if it only changed one function.

3. **Virtual inheritance overhead.** Every pass inherited from a base class via virtual dispatch. The NPM uses CRTP (Curiously Recurring Template Pattern) and templates, avoiding vtable overhead.

4. **Difficult to compose.** Adding a pass at a specific point in the pipeline required modifying the pass manager setup code. The NPM supports textual pipeline descriptions (`-passes='instcombine,gvn'`) and plugin extension points.

5. **No proxy analysis support.** The LPM couldn't express cross-scope analysis dependencies cleanly (e.g., a function pass needing a module-level analysis).

The NPM addresses these:
- **Explicit results:** `auto &DT = AM.getResult<DominatorTreeAnalysis>(F)` — clear what you're requesting.
- **Lazy computation:** Analyses are computed on demand and cached.
- **Fine-grained invalidation:** `PreservedAnalyses` reports exactly what changed.
- **Composable pipelines:** Text-based pipeline descriptions, extension points for plugins.

## Consequences

**Positive:**
- Cleaner, more maintainable pass development
- Better compile-time performance (lazy analysis, better invalidation)
- Textual pipeline descriptions for testing and experimentation
- Plugin extension points for downstream projects

**Negative:**
- Long migration period (both PMs coexisted for years)
- Some backend passes still use the legacy PM
- Learning curve for contributors familiar with the old system

## Trail

- NPM design: `include/llvm/IR/PassManager.h`
- Pipeline construction: `lib/Passes/PassBuilderPipelines.cpp`
- Pass registry: `lib/Passes/PassRegistry.def`
- The opt tool defaults to NPM: `tools/opt/opt.cpp`
