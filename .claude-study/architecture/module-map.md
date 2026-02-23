# LLVM Module Map

A detailed breakdown of every major directory in the `llvm/` subtree and the top-level `llvm-project/` monorepo.

---

## Top-Level Subprojects (`llvm-project/`)

| Directory | Description |
|-----------|-------------|
| `llvm/` | Core LLVM libraries: IR, optimizer, code generator, MC layer, tools |
| `clang/` | C/C++/ObjC/ObjC++ frontend — parser, Sema, AST, CodeGen to LLVM IR |
| `clang-tools-extra/` | Extra Clang-based developer tools: clang-tidy, clangd (LSP server), clang-include-fixer |
| `lld/` | The LLVM linker — supports ELF, COFF, Mach-O, and WebAssembly formats |
| `lldb/` | The LLVM debugger — scriptable via Python, uses Clang for expression evaluation |
| `mlir/` | Multi-Level IR framework — extensible IR infrastructure for domain-specific compilers |
| `flang/` | Fortran frontend — parses Fortran, lowers to FIR (Fortran IR) then to LLVM IR |
| `flang-rt/` | Flang Fortran runtime library |
| `bolt/` | Binary Optimization and Layout Tool — post-link binary optimizer using profile data |
| `polly/` | Polyhedral loop optimizer — automatic loop parallelization and tiling using the polyhedral model |
| `compiler-rt/` | Runtime libraries: sanitizers (ASan, MSan, TSan, UBSan), builtins, profiling, scudo allocator |
| `libcxx/` | libc++ — the LLVM C++ standard library implementation |
| `libcxxabi/` | libc++abi — the C++ ABI library (exception handling, RTTI) |
| `libunwind/` | Stack unwinding library |
| `libclc/` | OpenCL C standard library implementation |
| `libsycl/` | SYCL runtime library for heterogeneous computing |
| `openmp/` | OpenMP runtime library (`libomp`) |
| `orc-rt/` | ORC JIT runtime support library |
| `offload/` | GPU/accelerator offloading infrastructure |
| `cross-project-tests/` | Integration tests that span multiple subprojects |
| `cmake/` | Shared CMake modules used across all subprojects |
| `runtimes/` | CMake infrastructure for building runtime libraries as a separate step |
| `third-party/` | Vendored third-party code (Google Benchmark, Google Test) |
| `utils/` | Shared scripts and utilities |

---

## LLVM Core (`llvm/`) — Directory Structure

### `llvm/include/llvm/` — Public Headers

Every public C++ header lives here, organized by subsystem:

| Directory | Responsibility |
|-----------|---------------|
| `IR/` | The LLVM Intermediate Representation — `Value.h`, `Module.h`, `Function.h`, `BasicBlock.h`, `Instruction.h`, `Instructions.h`, `Type.h`, `DerivedTypes.h`, `Constants.h`, `IRBuilder.h`, `LLVMContext.h`, `PassManager.h` |
| `Transforms/` | Headers for optimization passes — `Scalar/`, `IPO/`, `Vectorize/`, `InstCombine/`, `Utils/`, `Coroutines/` |
| `Analysis/` | Headers for analysis passes — `AliasAnalysis.h`, `LoopInfo.h`, `DominatorTree.h`, `ScalarEvolution.h`, `MemorySSA.h`, `ValueTracking.h`, `LazyValueInfo.h` |
| `CodeGen/` | Code generation framework — `SelectionDAG/`, `MachineFunction.h`, `MachineInstr.h`, `MachineBasicBlock.h`, `TargetInstrInfo.h`, `TargetRegisterInfo.h`, `GlobalISel/` |
| `CodeGenTypes/` | Machine-level type definitions shared between IR and CodeGen |
| `MC/` | Machine Code layer — `MCInst.h`, `MCStreamer.h`, `MCAsmParser.h`, `MCCodeEmitter.h`, `MCObjectFileInfo.h` |
| `Target/` | Target abstraction — `TargetMachine.h`, `TargetOptions.h`, `TargetLowering.h` |
| `TargetParser/` | Target triple and feature string parsing |
| `ADT/` | Abstract Data Types — `SmallVector.h`, `StringRef.h`, `ArrayRef.h`, `DenseMap.h`, `FoldingSet.h`, `ilist.h`, `Twine.h`, `APInt.h`, `APFloat.h` |
| `Support/` | Platform abstraction and utilities — `raw_ostream.h`, `CommandLine.h`, `Casting.h`, `Error.h`, `ErrorHandling.h`, `Allocator.h`, `FileSystem.h`, `MemoryBuffer.h`, `Timer.h` |
| `Passes/` | New Pass Manager infrastructure — `PassBuilder.h`, `PassPlugin.h`, `StandardInstrumentations.h` |
| `AsmParser/` | Assembly (`.ll` file) parser interface |
| `Bitcode/` | Bitcode (`.bc` file) reader/writer interfaces |
| `Bitstream/` | Low-level bitstream reader/writer (underlying format for bitcode) |
| `BinaryFormat/` | Binary format definitions — ELF, COFF, MachO, DWARF, XCOFF constants |
| `DebugInfo/` | Debug information handling — DWARF, CodeView, PDB, BTF |
| `Object/` | Object file reading/writing — ELF, COFF, MachO, Wasm, XCOFF |
| `ExecutionEngine/` | JIT compilation — ORC (On-Request Compilation), MCJIT, interpreter |
| `LTO/` | Link-Time Optimization interfaces |
| `Linker/` | IR-level linking (merging modules) |
| `Frontend/` | Shared frontend utilities — OpenMP directive handling, HLSL support |
| `ProfileData/` | Profile-guided optimization data reading/writing |
| `Remarks/` | Optimization remark infrastructure |
| `TableGen/` | TableGen library interfaces |
| `Demangle/` | Symbol demangling (Itanium, Microsoft, Rust, D) |
| `XRay/` | XRay function-call tracing support |
| `Telemetry/` | Telemetry framework |
| `SandboxIR/` | Experimental Sandbox IR layer |
| `Testing/` | Test utilities |

### `llvm/lib/` — Implementation Libraries

Each directory under `lib/` corresponds to a linkable LLVM library:

| Directory | Files | Description |
|-----------|-------|-------------|
| `IR/` | ~76K LOC | Core IR implementation — Value, Type, Module, Instructions, Verifier, AsmWriter, IRBuilder, PassManager |
| `Transforms/Scalar/` | 82 files | Single-function optimizations — SROA, GVN, LICM, LoopUnroll, SimplifyCFG, ADCE, IndVarSimplify, etc. |
| `Transforms/IPO/` | | Interprocedural optimizations — Inliner, GlobalDCE, ArgumentPromotion, FunctionAttrs, etc. |
| `Transforms/Vectorize/` | | Auto-vectorization — LoopVectorize, SLPVectorizer, VectorCombine |
| `Transforms/InstCombine/` | | Instruction combining — algebraic simplification, canonicalization |
| `Transforms/Utils/` | | Transformation utilities — LoopSimplify, LCSSA, Mem2Reg, SSAUpdater, CloneFunction |
| `Transforms/AggressiveInstCombine/` | | More aggressive instruction combining |
| `Transforms/Coroutines/` | | Coroutine lowering passes |
| `Transforms/Instrumentation/` | | Sanitizer and profiling instrumentation passes |
| `Transforms/ObjCARC/` | | Objective-C ARC optimization |
| `Transforms/CFGuard/` | | Control Flow Guard instrumentation (Windows) |
| `Transforms/HipStdPar/` | | HIP standard parallelism support |
| `Analysis/` | 127 files | All analysis pass implementations |
| `CodeGen/` | 258 files | Target-independent code generation — instruction selection, register allocation, scheduling, prologue/epilogue insertion |
| `CodeGen/AsmPrinter/` | | Assembly printing from MachineInstr |
| `CodeGen/SelectionDAG/` | | SelectionDAG-based instruction selection |
| `CodeGen/GlobalISel/` | | Global Instruction Selection (newer alternative to SelectionDAG) |
| `Target/` | 30+ dirs | Target-specific backends (one per architecture) |
| `MC/` | | Machine Code layer — encoding, assembly parsing, object file emission |
| `AsmParser/` | | `.ll` text IR parser |
| `Bitcode/` | | `.bc` bitcode reader/writer |
| `Object/` | | Object file format reading |
| `ExecutionEngine/` | | JIT engines — ORC, MCJIT, RuntimeDyld, Interpreter |
| `LTO/` | | Link-Time Optimization implementation |
| `Linker/` | | IR linker (module merging) |
| `Support/` | | Platform abstraction, I/O, allocation, signal handling, threading |
| `TableGen/` | | TableGen library (used by `llvm-tblgen` tool) |
| `DebugInfo/` | | DWARF, CodeView, PDB, symbolizer |
| `ProfileData/` | | PGO profile data readers and writers |
| `BinaryFormat/` | | Format-specific constants and utilities |
| `Demangle/` | | Demangling implementations |
| `Passes/` | | New Pass Manager pipeline construction (`PassBuilder.cpp`) |
| `SandboxIR/` | | Experimental sandboxed IR layer |
| `FuzzMutate/` | | Fuzzing mutation strategies for LLVM IR |

### `llvm/tools/` — Command-Line Tools

| Tool | Description |
|------|-------------|
| `opt` | The LLVM optimizer — reads IR, runs passes, writes IR |
| `llc` | The LLVM static compiler — lowers IR to assembly or object code |
| `lli` | The LLVM interpreter / JIT executor |
| `llvm-as` | Assembler: `.ll` (text) → `.bc` (bitcode) |
| `llvm-dis` | Disassembler: `.bc` → `.ll` |
| `llvm-link` | IR linker: merges multiple `.bc` files |
| `llvm-ar` | Archive tool (also implements `ranlib`, `lib`, `dlltool`) |
| `llvm-nm` | Symbol table lister |
| `llvm-objdump` | Object file disassembler/dumper |
| `llvm-objcopy` | Object file transformer |
| `llvm-readobj` | Object file reader (also `llvm-readelf`) |
| `llvm-mc` | Machine code tool — assemble, disassemble, encode |
| `llvm-mca` | Machine Code Analyzer — static performance analysis |
| `llvm-dwarfdump` | DWARF debug info dumper |
| `llvm-symbolizer` | Address-to-symbol resolver (used by sanitizers) |
| `llvm-profdata` | Profile data manipulation |
| `llvm-cov` | Code coverage tool |
| `llvm-lto` / `llvm-lto2` | LTO tools |
| `llvm-reduce` | Test case reducer for LLVM IR |
| `bugpoint` | Legacy test case reducer |
| `llvm-exegesis` | Instruction benchmarking tool |
| `dsymutil` | DWARF linking tool (macOS) |
| `llvm-config` | Build configuration query tool |
| `llvm-jitlink` | JIT linker test tool |
| `llvm-ir2vec` | IR embedding tool |

### `llvm/test/` — Regression Tests

Uses LLVM's `lit` (LLVM Integrated Tester) framework with `FileCheck` for pattern-based output verification. Tests are organized by subsystem and tool.

### `llvm/unittests/` — Unit Tests

Google Test-based C++ unit tests for individual libraries.

### `llvm/utils/` — Development Utilities

- `lit/` — the LLVM Integrated Tester
- `FileCheck/` — pattern matching tool for tests
- `TableGen/` — TableGen tool
- `UpdateTestChecks/` — scripts to auto-update FileCheck lines in tests
- `gn/` — GN build system files (alternative to CMake)
- `vim/`, `emacs/` — editor syntax highlighting for `.ll` and `.td` files

### `llvm/benchmarks/` — Performance Benchmarks

Google Benchmark-based microbenchmarks for critical LLVM components.

### `llvm/bindings/` — Language Bindings

- `python/` — Python bindings for the LLVM C API

### `llvm/docs/` — Documentation

reStructuredText documentation built with Sphinx. Covers getting started, language reference, pass writing guides, coding standards, and backend development.

### `llvm/examples/` — Example Code

Example programs demonstrating LLVM API usage: JIT compilation, IR construction, pass writing.
