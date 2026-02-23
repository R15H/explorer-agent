# Potential Improvements

Larger ideas for features or refactors identified during codebase study.

---

## 1. Complete GlobalISel Adoption

**Area:** `lib/CodeGen/GlobalISel/`, all target backends
**Current state:** GlobalISel is the default for AArch64 at `-O0`. Other targets and optimization levels still use SelectionDAG.
**Opportunity:** Help bring GlobalISel to parity with SelectionDAG for more targets and higher optimization levels. The 171 TODO/FIXME comments in GlobalISel suggest active development with known gaps.

---

## 2. Legacy Pass Manager Removal

**Area:** `lib/IR/LegacyPassManager.cpp`, various backend passes
**Current state:** The New Pass Manager is the default for the optimization pipeline. Some backend (CodeGen) passes still use the legacy PM.
**Opportunity:** Help migrate remaining legacy PM usage in the backend to the new PM, bringing the project closer to removing the legacy PM entirely.

---

## 3. Improved Optimization Remarks

**Area:** `lib/Remarks/`, `include/llvm/Remarks/`
**Current state:** Optimization remarks exist but are inconsistently used across passes.
**Opportunity:** Add optimization remarks to passes that lack them, improve remark quality, create better tooling for analyzing remarks.

---

## 4. Better Debug Info Preservation

**Area:** All transformation passes, `lib/Transforms/Utils/Local.cpp`
**Current state:** Debug info is often lost or corrupted by optimization passes. The `debugify` pass (`-debugify-each`) detects this but many passes still have issues.
**Opportunity:** Systematically improve debug info handling in transformation passes. Each fix improves the debugging experience for every user of LLVM-based compilers.

---

## 5. SandboxIR Maturation

**Area:** `lib/SandboxIR/`, `include/llvm/SandboxIR/`
**Current state:** Experimental. SandboxIR provides a safe wrapper around LLVM IR that can track and undo changes.
**Opportunity:** Help develop this experimental layer, which could enable speculative optimizations and better pass isolation.

---

## 6. MCA (Machine Code Analyzer) Expansion

**Area:** `lib/MCA/`, `tools/llvm-mca/`
**Current state:** llvm-mca provides static performance analysis for instruction sequences. Target support varies.
**Opportunity:** Improve scheduling models for more microarchitectures, add pipeline visualization, improve throughput/latency predictions.

---

## 7. MLIR ↔ LLVM Dialect Improvements

**Area:** `mlir/lib/Dialect/LLVMIR/`
**Current state:** MLIR has an LLVM dialect for representing LLVM IR within the MLIR framework.
**Opportunity:** Improve the fidelity of the MLIR ↔ LLVM IR translation, especially for advanced features like exception handling, debug info, and target-specific intrinsics.
