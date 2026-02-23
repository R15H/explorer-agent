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

### 3. PointerIntPair — Pack Free Bits into Aligned Pointers

```cpp
// One uintptr_t stores BOTH a pointer AND a small integer.
// Pointers to 8-byte-aligned objects have 3 unused low bits.
template <typename PointerTy, unsigned IntBits, typename IntType = unsigned>
class PointerIntPair {
  intptr_t Value;  // pointer bits | int bits, packed together
public:
  PointerTy getPointer() const;  // masks off low bits
  IntType   getInt() const;      // shifts and masks low bits
  void setPointerAndInt(PointerTy Ptr, IntType Int);
};

// Usage: store a pointer + a 1-bit flag in a single word
PointerIntPair<Instruction*, 1, bool> Pair(myInst, /*isSpecial=*/true);
```

**Steal this:** Any pointer to an aligned object has free bits at the bottom. Use them to store tags, flags, or small enums — zero extra memory. Useful for tagged pointers in GC systems, state machines, graph edges with annotations, or any struct where you'd otherwise add a `bool` field next to a pointer (wasting 7 bytes to padding).

### 4. BumpPtrAllocator — Bump a Pointer, Never Free Individually

```cpp
void *Allocate(size_t Size, Align Alignment) {
  uintptr_t AlignedPtr = alignAddr(CurPtr, Alignment);
  if (AlignedPtr + Size <= End) {   // fits in current slab?
    CurPtr = AlignedPtr + Size;     // bump the pointer
    return (void *)AlignedPtr;      // done — no free list, no metadata
  }
  return AllocateSlow(Size, Alignment);  // get a new slab
}
// Destructor frees ALL slabs at once. No individual delete.
```

**Steal this:** When objects share a common lifetime (one HTTP request, one compiler pass, one game frame), allocate them by bumping a pointer into a pre-allocated slab. Free everything at once when the phase ends. This is 10-100x faster than `malloc`/`free` for small allocations. The fast path is three operations: align, compare, bump.

### 5. Custom RTTI (classof) — Type Checks Without Virtual Dispatch

```cpp
// Base class stores an integer discriminator
class Value {
  unsigned SubclassID;
};

// Each derived class implements a static check
class BranchInst : public Instruction {
public:
  static bool classof(const Instruction *I) {
    return I->getOpcode() == Instruction::Br;  // one integer comparison
  }
};

// Usage — combines check + cast in one step
if (auto *BI = dyn_cast<BranchInst>(SomeValue)) { /* use BI */ }
```

**Steal this:** Store a type tag (enum/int) in the base class. Add a `static bool classof(const Base*)` to each subclass. This replaces `dynamic_cast` with a single integer comparison — no vtable lookup, no RTTI metadata. Works for any class hierarchy where you frequently need "is this a Foo?" checks (AST nodes, event types, message variants).

### 6. StringRef — Non-Owning String View Done Right

```cpp
class StringRef {
  const char *Data = nullptr;
  size_t Length = 0;
public:
  StringRef(std::nullptr_t) = delete;           // block dangerous null conversion
  /*implicit*/ StringRef(const char *Str);      // from C string
  /*implicit*/ StringRef(const std::string &S);  // from std::string — no copy

  StringRef substr(size_t Start, size_t N) const {  // zero-copy substring
    return StringRef(Data + Start, std::min(N, Length - Start));
  }
};
```

**Steal this:** Any function that *reads* a string but doesn't need to own it should take a non-owning view (pointer + length). This eliminates copies at API boundaries. The `= delete` on `nullptr_t` prevents the most common misuse. LLVM built this before `std::string_view` existed — and the deleted-nullptr trick is something `string_view` still doesn't have.

### 7. Twine — Lazy String Concatenation Tree

```cpp
// "file:" + filename + ":" + lineNo  builds a binary tree.
// NO string allocation until you actually need the result.
class Twine {
  enum NodeKind { CStringKind, StringRefKind, DecIKind, CharKind, ... };
  union Child {
    const char *cString;
    const StringRef *stringRef;
    int decI;
    char character;
  };
  Child LHS, RHS;       // two children = binary tree
  NodeKind LHSKind, RHSKind;

  // Only materialized when needed:
  std::string str() const;                    // flatten into a string
  void print(raw_ostream &OS) const;          // write directly to stream
};
```

**Steal this:** When you concatenate strings just to write them to a log/stream/diagnostic, you're allocating and copying for nothing. Instead, build a lightweight tree of *references* to the pieces. Materialize only when the output is actually needed. This is especially valuable in hot paths where the message is often discarded (debug logging, verbose diagnostics).

### 8. TrailingObjects — Variable-Length Objects in a Single Allocation

```cpp
// Allocate a fixed-size header + variable-length array in ONE malloc.
class AttributeList : private TrailingObjects<AttributeList, Attribute> {
  unsigned NumAttrs;
  size_t numTrailingObjects(OverloadToken<Attribute>) const { return NumAttrs; }

public:
  static AttributeList *create(unsigned N) {
    void *Mem = malloc(totalSizeToAlloc<Attribute>(N));  // one allocation
    return new (Mem) AttributeList(N);
  }
  ArrayRef<Attribute> getAttrs() const {
    return {getTrailingObjects<Attribute>(), NumAttrs};  // pointer arithmetic, no indirection
  }
};
```

**Steal this:** When an object always has "N items after it" (AST node + operands, packet header + payload, message + variable body), allocate them together. One `malloc` instead of two. The data is contiguous in memory — better cache locality, fewer allocations, simpler lifetime management. The `TrailingObjects` mixin handles the alignment math for you, but the core idea works in any language: `malloc(sizeof(Header) + n * sizeof(Item))`.

---

*For deeper exploration, see the full analysis in the [.claude-study/](./README.md) directory.*
