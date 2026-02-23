# LLVM Glossary

Project-specific terminology used throughout the LLVM codebase and documentation.

---

## Core Concepts

**IR (Intermediate Representation)**
The core language of LLVM. A typed, SSA-based representation that is target-independent. Exists in three equivalent forms: in-memory C++ objects, textual assembly (`.ll`), and binary bitcode (`.bc`).

**SSA (Static Single Assignment)**
A property of the IR where every variable is assigned exactly once and every use is dominated by its definition. Control flow merges use `phi` nodes to select between values from different predecessors.

**Module**
The top-level IR container. Corresponds roughly to a translation unit. Contains global variables, functions, type definitions, metadata, and named metadata. Class: `llvm::Module` (`include/llvm/IR/Module.h`).

**Function**
A callable entity within a Module. Contains a list of `BasicBlock`s and `Argument`s. Class: `llvm::Function` (`include/llvm/IR/Function.h`).

**BasicBlock**
A maximal sequence of instructions with no branches except at the end. Instructions execute sequentially from first to last. The last instruction must be a **terminator** (branch, return, switch, etc.). Class: `llvm::BasicBlock` (`include/llvm/IR/BasicBlock.h`).

**Instruction**
A single SSA operation (add, load, store, call, branch, etc.). Each produces at most one value (the instruction itself is the value). Class: `llvm::Instruction` (`include/llvm/IR/Instruction.h`).

**Value**
The base class for anything that has a type and a use list. Instructions, arguments, constants, functions, and global variables are all `Value`s. Class: `llvm::Value` (`include/llvm/IR/Value.h`).

**User**
A `Value` that references other `Value`s as operands. All `Instruction`s and `Constant`s are `User`s. Class: `llvm::User` (`include/llvm/IR/User.h`).

**Use**
An edge in the use-def graph. Connects a `User` to one of its operand `Value`s. Enables `RAUW` and user iteration. Class: `llvm::Use` (`include/llvm/IR/Use.h`).

**Type**
The type of a Value. LLVM types include `i1`, `i8`, `i32`, `i64` (integers of arbitrary width), `float`, `double`, `ptr` (opaque pointer), `<4 x i32>` (vectors), `[10 x i32]` (arrays), `{i32, float}` (structs), and function types. Class: `llvm::Type` (`include/llvm/IR/Type.h`).

**LLVMContext**
Owns and uniquifies types, constants, and metadata. Thread-safe boundary — different threads can use different contexts safely. Class: `llvm::LLVMContext` (`include/llvm/IR/LLVMContext.h`).

---

## Passes and Optimization

**Pass**
A unit of IR analysis or transformation. Registered with the pass manager and run as part of a pipeline.

**Analysis Pass**
A pass that computes information about the IR without modifying it. Results are cached by the pass manager. Examples: `DominatorTreeAnalysis`, `LoopAnalysis`, `AAManager`.

**Transformation Pass**
A pass that modifies the IR. Must declare which analyses it preserves (so the pass manager knows what to invalidate). Examples: `InstCombinePass`, `SROAPass`, `InlinerPass`.

**Pass Manager (PM)**
Schedules and runs passes, manages analysis caching and invalidation. The **New Pass Manager** (NPM, in `include/llvm/IR/PassManager.h`) replaced the **Legacy Pass Manager** (LPM, in `lib/IR/LegacyPassManager.cpp`).

**PassBuilder**
Constructs predefined optimization pipelines (O0, O1, O2, O3, Os, Oz) and handles pass registration. Class: `llvm::PassBuilder` (`include/llvm/Passes/PassBuilder.h`).

**CGSCC (Call Graph Strongly Connected Component)**
A group of mutually recursive functions. The CGSCC pass manager processes these groups together, enabling optimizations like inlining within recursive call chains.

---

## Specific Passes and Analyses

**SROA (Scalar Replacement of Aggregates)**
Decomposes `alloca` instructions into individual SSA values when possible. The primary pass for promoting memory to registers.

**InstCombine (Instruction Combining)**
Peephole optimizer that applies algebraic simplifications, canonicalization, and strength reduction to instructions.

**GVN (Global Value Numbering)**
Eliminates redundant computations by assigning value numbers to expressions and replacing duplicates.

**LICM (Loop Invariant Code Motion)**
Moves computations that don't change within a loop to outside the loop.

**ADCE (Aggressive Dead Code Elimination)**
Removes instructions whose results are never used, including across control flow.

**DSE (Dead Store Elimination)**
Removes stores to memory locations that are overwritten before being read.

**Mem2Reg**
Promotes `alloca` instructions to SSA registers by constructing phi nodes. Subsumed by SROA in practice.

**SimplifyCFG**
Simplifies control flow graphs — merges basic blocks, eliminates unreachable code, converts branches to select instructions.

**DominatorTree**
Analysis that computes dominance relationships between basic blocks. Block A dominates block B if every path from the entry to B goes through A.

**LoopInfo**
Analysis that identifies natural loops and their nesting structure.

**ScalarEvolution (SCEV)**
Analysis that computes closed-form expressions for how scalar values evolve across loop iterations. Central to loop optimizations.

**AliasAnalysis (AA)**
Analysis that determines whether two memory references may point to the same location. Results: MustAlias, MayAlias, NoAlias, PartialAlias.

**MemorySSA**
An SSA form for memory operations. Provides an efficient way to query which stores might affect a given load.

---

## Code Generation

**SelectionDAG**
A directed acyclic graph representation used during instruction selection. Each node represents an operation; edges represent data dependencies. Operates one basic block at a time.

**GlobalISel (Global Instruction Selection)**
The newer instruction selection framework. Operates on `MachineInstr` directly (no intermediate DAG). Supports cross-basic-block optimizations and is generally faster to compile.

**MachineFunction**
The machine-level equivalent of `Function`. Contains `MachineBasicBlock`s. Class: `llvm::MachineFunction` (`include/llvm/CodeGen/MachineFunction.h`).

**MachineInstr (MI)**
A machine-level instruction with target-specific opcodes and `MachineOperand`s (physical/virtual registers, immediates, memory references). Class: `llvm::MachineInstr` (`include/llvm/CodeGen/MachineInstr.h`).

**MIR (Machine IR)**
The textual serialization format for MachineFunction, analogous to `.ll` files for LLVM IR. Used for testing machine-level passes.

**MCInst**
A lightweight, flat instruction representation in the MC layer. Just an opcode and operands — no register allocation or SSA information. The final form before binary encoding.

**MC Layer (Machine Code)**
The lowest-level abstraction. Handles assembly parsing, instruction encoding, object file emission, and disassembly.

**Register Allocation (RegAlloc)**
The process of mapping virtual registers to physical machine registers. Algorithms: Greedy (default), PBQP, Basic, Fast (for -O0).

**TableGen**
A domain-specific language (`.td` files) used to declaratively describe target instruction sets, register files, calling conventions, and scheduling models. The `llvm-tblgen` tool generates C++ from `.td` files.

**TargetMachine**
Abstract interface representing a specific target (architecture + features + ABI). Each backend provides a concrete subclass (e.g., `X86TargetMachine`).

**TargetLowering**
Describes how to lower LLVM IR operations to target-specific SelectionDAG nodes. Handles type legalization, operation legalization, and calling convention lowering.

---

## Data Structures (ADT)

**SmallVector**
A vector with inline storage for a small number of elements. Avoids heap allocation for the common case. `SmallVector<T, N>` stores up to `N` elements inline.

**StringRef**
A non-owning reference to a string (pointer + length). Avoids copies when passing string data around. Does **not** guarantee null-termination.

**ArrayRef**
A non-owning reference to a contiguous array of elements. The read-only counterpart to `MutableArrayRef`.

**Twine**
A lightweight string concatenation helper that defers actual concatenation until the result is needed. Used for efficient message construction.

**DenseMap**
A hash map optimized for small keys (pointers, small integers). Uses open addressing with quadratic probing. More cache-friendly than `std::unordered_map`.

**DenseSet**
The set counterpart of DenseMap.

**StringMap**
A hash map keyed by strings, with the key stored inline in the hash table entry.

**FoldingSet**
A uniquing hash set where identity is determined by a "profile" — a sequence of values hashed together. Used for uniquifying IR types and constants.

**ilist (intrusive list)**
A doubly-linked list where the prev/next pointers are embedded in the list elements themselves. Used for `Instruction`s in `BasicBlock`, `BasicBlock`s in `Function`. Supports O(1) splice, insert, and remove.

**BumpPtrAllocator**
An arena allocator that allocates memory from large slabs. Individual allocations cannot be freed; the entire arena is freed at once. Extremely fast allocation.

**APInt (Arbitrary Precision Integer)**
Integer type that can represent values of any bit width. Used throughout the IR for constant integers and in analyses like known-bits computation.

**APFloat**
Arbitrary precision floating point. Supports all IEEE 754 formats plus some target-specific formats.

---

## RTTI and Casting

**isa\<T\>(V)**
Returns `true` if `V` is an instance of type `T`. No cast performed.

**cast\<T\>(V)**
Unconditional cast. Asserts that `V` is an instance of `T`. Use when you know the type.

**dyn_cast\<T\>(V)**
Conditional cast. Returns `nullptr` if `V` is not an instance of `T`. Equivalent to `if (isa<T>(V)) return cast<T>(V)`.

**dyn_cast_or_null\<T\>(V)**
Like `dyn_cast`, but also handles `V == nullptr` (returns `nullptr` in that case).

**RAUW (Replace All Uses With)**
`Value::replaceAllUsesWith(Value *V)` — replaces all uses of a value with another value. The fundamental IR mutation operation.

---

## Build and Infrastructure

**lit (LLVM Integrated Tester)**
LLVM's test runner. Executes test files containing `RUN:` directives and uses `FileCheck` for output verification.

**FileCheck**
A pattern matching tool that verifies output matches expected patterns specified by `CHECK:` directives.

**Bitcode**
The binary serialization format for LLVM IR (`.bc` files). More compact and faster to read than textual IR.

**LTO (Link-Time Optimization)**
Optimization performed at link time by combining bitcode modules and running the optimizer on the merged program.

**ThinLTO**
A scalable form of LTO that uses module summaries for cross-module analysis, then optimizes modules in parallel.

**ORC (On-Request Compilation)**
LLVM's JIT compilation framework. Supports lazy compilation, concurrent compilation, and remote execution.

**BOLT (Binary Optimization and Layout Tool)**
Post-link binary optimizer that reorders functions and basic blocks based on profile data.
