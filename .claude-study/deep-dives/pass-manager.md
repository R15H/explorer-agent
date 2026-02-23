# Deep Dive: The LLVM Pass Manager

LLVM's pass manager is the orchestration engine that runs analyses and transformations on the IR. Understanding it is essential for anyone writing or debugging optimization passes.

---

## Two Pass Managers

LLVM has two pass manager implementations:

1. **Legacy Pass Manager (LPM)** — the original, being phased out. Lives in `lib/IR/LegacyPassManager.cpp` (~1,734 lines). Uses virtual inheritance and `getAnalysis<T>()` for dependency resolution.

2. **New Pass Manager (NPM)** — the current default. Lives in `include/llvm/IR/PassManager.h` and `lib/Passes/`. Uses templates and explicit analysis results. All new passes should use NPM.

The key difference: in the legacy PM, passes register their dependencies statically and the PM figures out the order. In the new PM, passes explicitly request analysis results, and the PM tracks invalidation.

---

## New Pass Manager Architecture

### Pass Types

Passes are C++ classes with a `run()` method. The template parameter determines the IR unit:

```cpp
// A function pass
class MyPass : public PassInfoMixin<MyPass> {
public:
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &AM) {
    // Get analyses
    auto &DT = AM.getResult<DominatorTreeAnalysis>(F);

    // Do transformation...

    // Report what was preserved
    return PreservedAnalyses::all();  // or PreservedAnalyses::none()
  }
};
```

Pass hierarchy by scope:
- **ModulePass** — `run(Module &M, ModuleAnalysisManager &MAM)`
- **CGSCCPass** — `run(LazyCallGraph::SCC &C, CGSCCAnalysisManager &AM, ...)`
- **FunctionPass** — `run(Function &F, FunctionAnalysisManager &FAM)`
- **LoopPass** — `run(Loop &L, LoopAnalysisManager &LAM, ...)`

### Analysis Passes

Analyses compute information without modifying the IR:

```cpp
class MyAnalysis : public AnalysisInfoMixin<MyAnalysis> {
  friend AnalysisInfoMixin<MyAnalysis>;
  static AnalysisKey Key;  // Unique key for this analysis

public:
  struct Result {
    // Analysis results go here
  };

  Result run(Function &F, FunctionAnalysisManager &AM) {
    // Compute analysis...
    return Result{...};
  }
};
```

Results are cached by the analysis manager. When a transformation pass runs:
1. It calls `AM.getResult<SomeAnalysis>(F)` to get cached or freshly computed results
2. After the transform, it returns `PreservedAnalyses` indicating which analyses are still valid
3. The PM invalidates caches for analyses not in the preserved set

### PreservedAnalyses

The invalidation protocol. A transformation returns one of:
- `PreservedAnalyses::all()` — nothing was changed, all analyses are still valid
- `PreservedAnalyses::none()` — everything might have changed, invalidate all
- `PreservedAnalyses::allInSet<CFGAnalyses>()` — the CFG didn't change, but other things did
- Custom: `PA.preserve<DominatorTreeAnalysis>()` — preserve specific analyses

**File:** `include/llvm/IR/PassManager.h`

---

## PassBuilder — Constructing Pipelines

`PassBuilder` (`include/llvm/Passes/PassBuilder.h`, `lib/Passes/PassBuilder.cpp`) is responsible for:

1. **Registering all passes** — both built-in and plugin passes
2. **Constructing predefined pipelines** — O0, O1, O2, O3, Os, Oz
3. **Parsing textual pipeline descriptions** — e.g., `"function(instcombine,sroa)"`

### Pipeline Construction

The key methods:

```cpp
// Build the default pipeline for a given optimization level
ModulePassManager buildPerModuleDefaultPipeline(OptimizationLevel Level);

// Build the ThinLTO pre-link pipeline
ModulePassManager buildThinLTOPreLinkDefaultPipeline(OptimizationLevel Level);

// Parse a textual pipeline description
Error parsePassPipeline(ModulePassManager &MPM, StringRef PipelineText);
```

### The O2 Pipeline (simplified)

Defined in `lib/Passes/PassBuilderPipelines.cpp`:

```
Module Pipeline:
├── Annotation2MetadataPass
├── ForceFunctionAttrsPass
├── InferFunctionAttrsPass
├── CoroEarlyPass
├── LowerExpectIntrinsicPass
│
├── [Early Function Simplification]
│   ├── SROA
│   ├── EarlyCSEPass
│   ├── SimplifyCFGPass
│   ├── InstCombinePass
│   └── LibCallsShrinkWrapPass
│
├── [IP Optimization - CGSCC Pipeline]
│   ├── InlinerPass
│   ├── [Function Pipeline per SCC]:
│   │   ├── SROA
│   │   ├── InstCombinePass
│   │   ├── JumpThreadingPass
│   │   ├── CorrelatedValuePropagationPass
│   │   ├── [Loop Pipeline]:
│   │   │   ├── LoopInstSimplifyPass
│   │   │   ├── LoopSimplifyCFGPass
│   │   │   ├── LICMPass
│   │   │   ├── LoopRotatePass
│   │   │   ├── SimpleLoopUnswitchPass
│   │   │   └── IndVarSimplifyPass
│   │   ├── MemCpyOptPass
│   │   ├── DSEPass
│   │   ├── [Loop Pipeline]:
│   │   │   ├── LoopIdiomRecognizePass
│   │   │   ├── LoopDeletionPass
│   │   │   └── LoopUnrollPass
│   │   ├── GVNPass
│   │   ├── ADCEPass
│   │   └── SimplifyCFGPass
│   └── PostOrderFunctionAttrsPass
│
├── [Module-level optimizations]
│   ├── GlobalDCEPass
│   ├── ConstantMergePass
│   ├── [Loop Vectorization Pipeline]:
│   │   ├── LoopVectorizePass
│   │   ├── SLPVectorizerPass
│   │   └── VectorCombinePass
│   └── ...
│
├── CoroCleanupPass
└── GlobalDCEPass (final cleanup)
```

### Extension Points

PassBuilder provides hooks for plugins to inject passes at specific points:

```cpp
// Called before the function simplification pipeline
PB.registerPeepholeEPCallback(
    [](FunctionPassManager &FPM, OptimizationLevel Level) {
      FPM.addPass(MyCustomPass());
    });

// Called after vectorization
PB.registerVectorizerStartEPCallback(...);
```

**Files:**
- `include/llvm/Passes/PassBuilder.h`
- `lib/Passes/PassBuilderPipelines.cpp` — pipeline definitions
- `lib/Passes/PassRegistry.def` — registry of all known passes

---

## How opt Invokes the Pipeline

The `opt` tool (`tools/opt/opt.cpp`) is the main driver for running optimization passes on IR:

1. Parse command-line options (input file, pass list, optimization level)
2. Read the input `.ll` or `.bc` file into a `Module`
3. Create a `PassBuilder`
4. Either parse a textual pipeline (`-passes='instcombine,gvn'`) or build a default pipeline (`-O2`)
5. Run the pipeline on the module
6. Write the output `.ll` or `.bc`

```
$ opt -passes='instcombine,sroa' -S input.ll -o output.ll
$ opt -passes='default<O2>' -S input.ll -o output.ll
```

---

## Analysis Manager Internals

The analysis manager (`AnalysisManager<IRUnitT>`) maintains:

- A **registry** of analysis pass factories (keyed by `AnalysisKey`)
- A **cache** of computed results (keyed by `(AnalysisKey, IRUnit)`)
- An **invalidation** mechanism that removes stale results

When `AM.getResult<T>(F)` is called:
1. Look up the cache for `(T::Key, &F)`
2. If found and valid, return it
3. If not, call `T::run(F, AM)` to compute the result
4. Store in cache
5. Return

When invalidation happens (after a transform), the PM calls:
```cpp
AM.invalidate(F, PreservedAnalyses);
```
This walks the cache and removes any entries whose analyses are not in the preserved set. Analyses can implement custom `invalidate()` methods for fine-grained control.

---

## The Legacy Pass Manager (for reference)

Still used in some backends and older code. Key differences:

- Passes inherit from `ModulePass`, `FunctionPass`, `LoopPass`, etc.
- Dependencies declared in `getAnalysisUsage(AnalysisUsage &AU)`
- Results obtained via `getAnalysis<T>()`
- Registration via `RegisterPass<T>` or `INITIALIZE_PASS_*` macros

```cpp
class MyLegacyPass : public FunctionPass {
  static char ID;
  MyLegacyPass() : FunctionPass(ID) {}

  void getAnalysisUsage(AnalysisUsage &AU) const override {
    AU.addRequired<DominatorTreeWrapperPass>();
    AU.setPreservesCFG();
  }

  bool runOnFunction(Function &F) override {
    auto &DT = getAnalysis<DominatorTreeWrapperPass>().getDomTree();
    // ...
    return Changed;
  }
};
```

**File:** `lib/IR/LegacyPassManager.cpp`
