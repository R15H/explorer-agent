# Bug Hypotheses and Fragile Areas

Areas identified during codebase study that appear fragile, under-tested, or prone to bugs.

---

## 1. Debug Info in Transformation Passes

**Files:** Most files in `lib/Transforms/`
**Observation:** Many transformation passes have inconsistent debug info handling. When instructions are replaced, moved, or deleted, debug locations and debug value intrinsics must be updated. The `salvageDebugInfo()` utility exists but is not universally used.

**Evidence:** The `debugify` test pass (`-debugify-each`) exists specifically to detect debug info loss, suggesting this is a known problem area. The `llvm/test/DebugInfo/` directory contains many regression tests for previously-found debug info bugs.

**Risk:** Users debugging optimized code see incorrect source locations or missing variable values.

---

## 2. MemCpyOptimizer Edge Cases

**File:** `lib/Transforms/Scalar/MemCpyOptimizer.cpp` — 14 TODO/FIXME markers
**Observation:** This pass has the highest density of TODO comments among scalar passes, suggesting many known but unhandled edge cases. Memory copying optimization interacts with alias analysis, lifetime markers, and exception handling in complex ways.

**Risk:** Missed optimizations or, worse, incorrect optimizations around memory copies.

---

## 3. RewriteStatepointsForGC Complexity

**File:** `lib/Transforms/Scalar/RewriteStatepointsForGC.cpp` — 23 TODO/FIXME markers
**Observation:** The highest absolute count of TODOs in any scalar transform. This pass converts normal call sites to GC statepoints, which is inherently complex due to interactions with the GC, exception handling, and deoptimization.

**Risk:** Incorrect statepoint placement or missing GC roots could cause GC-related crashes in languages using LLVM's GC support (e.g., some configurations of Go, Zig).

---

## 4. Dead Store Elimination False Positives

**File:** `lib/Transforms/Scalar/DeadStoreElimination.cpp` — 16 TODO/FIXME markers
**Observation:** DSE must determine that a store is not observable before removing it. This depends on alias analysis, which is conservative — but DSE's interaction with volatile operations, atomic operations, and exception handling creates tricky corner cases.

**Risk:** Incorrectly removing a store that is actually observable (correctness bug).

---

## 5. Loop Idiom Recognition Boundaries

**File:** `lib/Transforms/Scalar/LoopIdiomRecognize.cpp` — 18 TODO/FIXME markers
**Observation:** This pass recognizes loop patterns and replaces them with library calls (e.g., a byte-copying loop → `memcpy`). The pattern matching must be precise — false positives cause incorrect code.

**Risk:** Incorrect idiom recognition could replace a loop with a semantically different library call.

---

## 6. GlobalISel LegalizerHelper

**File:** `lib/CodeGen/GlobalISel/LegalizerHelper.cpp` — 47 TODO/FIXME markers
**Observation:** The highest TODO count of any file examined. Many generic operations lack proper legalization for certain type combinations. When GlobalISel encounters an unhandled case, it typically falls back to SelectionDAG, but missed cases could lead to assertion failures or incorrect code.

**Risk:** Assertion failures, fallback to slower SelectionDAG path, or potential miscompilations on targets using GlobalISel.

---

## General Fragility Indicators

- **Files with many TODO/FIXME comments** generally indicate known incomplete implementations.
- **Passes that interact with multiple analyses** (alias analysis + loop info + SCEV) have more surface area for bugs.
- **Recently active files with many bug-fix commits** (check `git log --oneline --since="6 months ago" -- <file>`) tend to be areas of active churn and potential instability.
- **Code paths guarded by `// Conservative` or `// Be safe`** comments often indicate areas where correctness was chosen over performance due to uncertainty — these might be overly conservative, creating missed optimization opportunities.
