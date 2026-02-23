# LLVM

## Date & Relevance

**Started:** 2000 (Chris Lattner's master's thesis at University of Illinois). Open-sourced 2003. Apache 2.0 license (with LLVM exception).

**Where it's used:**
- **Apple** — Clang/LLVM is the default compiler for macOS, iOS, and all Apple platforms. Swift compiles through LLVM.
- **Rust** — `rustc` uses LLVM as its code generation backend.
- **Android** — the Android NDK ships Clang/LLVM as the official C/C++ compiler.
- **Game consoles** — Sony uses LLVM for PS4/PS5 compilers. Nintendo and others have LLVM-based toolchains.
- **GPUs** — NVIDIA's CUDA compiler (nvcc) and AMD's ROCm stack both use LLVM for GPU code generation.
- **WebAssembly** — Emscripten compiles C/C++ to WebAssembly through LLVM.
- **30+ CPU architectures** — x86, ARM, RISC-V, PowerPC, MIPS, SPARC, SystemZ, and more.

If a new programming language needs a production compiler backend today, it almost certainly targets LLVM IR.

---

## What It Did Well for the First Time

**Compiler as a library, not a monolith.** Before LLVM, compilers (GCC, MSVC) were tightly coupled programs where the frontend, optimizer, and backend were deeply intertwined. LLVM proved that a compiler could be built as a collection of independent, reusable libraries with a stable intermediate representation (IR) as the contract between them.

This meant:
- New languages (Rust, Swift, Julia) could get a world-class optimizer and code generator for free by just emitting LLVM IR.
- New hardware targets only needed a backend — all existing frontends and optimizations work automatically.
- Tools like static analyzers, JIT compilers, and binary optimizers could reuse individual LLVM libraries without pulling in the whole compiler.

---

## Programming Patterns

**Custom RTTI** (`isa<>` / `cast<>` / `dyn_cast<>`) — Replaces C++ `dynamic_cast` with a static `classof()` method and an integer discriminator. Compiles down to a single integer comparison. Allows building with `-fno-rtti`, reducing binary size ~5-10%. See `llvm/Support/Casting.h`.

**Small Buffer Optimization** (`SmallVector<T, N>`) — Stores up to N elements inline (stack/object), heap-allocates only when exceeded. Most compiler vectors are small (2-8 elements), so this avoids millions of tiny heap allocations. Default N is chosen to fit one cache line (64 bytes). See `llvm/ADT/SmallVector.h`.

**Arena Allocation** (`BumpPtrAllocator`) — Allocates by bumping a pointer. Never frees individual objects — frees everything at once when the arena is destroyed. Compilers create millions of IR nodes per compilation; individual `malloc`/`free` would be ruinous. See `llvm/Support/Allocator.h`.

**Checked Errors** (`Error` / `Expected<T>`) — If you create an `Error` and don't check it before it's destroyed, the destructor aborts with a diagnostic. Move-only semantics prevent accidental loss. `Expected<T>` is the equivalent of Rust's `Result<T, E>`. See `llvm/Support/Error.h`.

---

## Design & Architectural Patterns

**Three-phase architecture.** Frontend (Clang) → IR → Backend, decoupled by a stable, typed, SSA-based intermediate representation. Any frontend can target any backend through this shared IR.

**Pass Manager pipeline.** Optimizations are composable passes that declare what analyses they need and what they preserve. Analyses are computed lazily and cached. The New Pass Manager uses templates (no virtual dispatch) and supports textual pipeline descriptions like `-passes='instcombine,gvn,loop-vectorize'`.

**TableGen — declarative code generation.** Target instruction sets, register files, calling conventions, and scheduling models are described in `.td` files (a domain-specific language). TableGen generates the C++ boilerplate. Adding a new instruction to a backend is a few lines of TableGen, not hundreds of lines of C++.

---

## Reusable Nuggets

### 1. SmallVector — Avoid Heap Allocation for Small Collections

```cpp
template <typename T, unsigned N>
class SmallVector : public SmallVectorImpl<T> {
  alignas(T) char InlineElts[N * sizeof(T)];  // inline storage
};

// Key insight: one check determines if we're on the stack or heap
bool isSmall() const { return BeginX == getFirstEl(); }
```

**Steal this:** Any time you have a collection that's *usually* small but *occasionally* large, embed a small fixed buffer inside the object. Fall back to heap only when it overflows. This one pattern eliminates the majority of small allocations in LLVM. Apply it to vectors, strings, sets — anything with a predictable common size.

### 2. Error Must-Check — Enforce Error Handling via Destructor

```cpp
class Error {
  bool Checked = false;
  // ...
  ~Error() {
    if (!Checked) {  // You forgot to handle this error
      dbgs() << "Unhandled Error:\n";
      abort();       // Crash immediately — don't silently swallow it
    }
  }
};
```

**Steal this:** If your API returns errors that callers might ignore, make ignoring them fatal. A move-only error type with a destructor assertion catches every unhandled error during development. This is Rust's `#[must_use]` + `Result<T, E>` implemented in plain C++. The cost is zero in success paths (just a null pointer + boolean flag).

---

*For deeper exploration, see the full analysis in the [.claude-study/](./README.md) directory.*
