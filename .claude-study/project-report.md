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

### 9. DenseMap — Open-Addressing Hash Map with Quadratic Probing

```cpp
// No linked lists. Buckets are contiguous in memory.
// Empty and tombstone keys mark bucket state — no separate metadata.
const BucketT *doFind(const LookupKeyT &Val) const {
  unsigned BucketNo = KeyInfoT::getHashValue(Val) & (NumBuckets - 1); // power-of-2 mask
  unsigned ProbeAmt = 1;
  while (true) {
    if (KeyInfoT::isEqual(Val, Bucket->getFirst())) return Bucket;  // found
    if (KeyInfoT::isEqual(Bucket->getFirst(), EmptyKey)) return nullptr;  // miss
    BucketNo += ProbeAmt++;   // quadratic probing: 1, 3, 6, 10, ...
    BucketNo &= NumBuckets - 1;
  }
}
```

**Steal this:** Use open addressing (all entries in one array) instead of chaining (linked lists per bucket). Cache locality alone makes this 2-5x faster than `std::unordered_map`. Tombstones (a special "deleted" marker) handle erasure without breaking probe chains. Power-of-2 bucket count turns modulo into a bitwise AND.

### 10. FoldingSet — Content-Addressed Uniquing (Interning)

```cpp
// "Have I seen this exact combination of fields before?"
void Profile(FoldingSetNodeID &ID) const {
  ID.AddInteger(TypeKind);     // hash the type kind
  ID.AddPointer(ReturnType);   // hash the return type pointer
  for (auto *Param : Params)
    ID.AddPointer(Param);      // hash each parameter type
}
// Lookup: if (Node *Existing = Set.FindNodeOrInsertPos(ID, InsertPos)) return Existing;
```

**Steal this:** When you create many objects that are structurally identical (types, AST nodes, cache keys), hash their contents and store them in a uniquing set. Return the existing instance instead of creating a duplicate. This is interning — same concept as Python's string interning or Java's `String.intern()`, but generalized to any composite object.

### 11. PointerUnion — Discriminated Union of Pointers in One Word

```cpp
// Store one of N pointer types in a single uintptr_t.
// The discriminator lives in the low bits (same trick as PointerIntPair).
PointerUnion<Instruction*, BasicBlock*, Function*> Val;

Val = myInstruction;                          // stores Instruction* + tag 0
if (auto *I = dyn_cast<Instruction*>(Val))    // check tag, extract pointer
  I->eraseFromParent();
```

**Steal this:** When a field can hold "either a Foo* or a Bar*", don't use a struct with a pointer + enum. Pack the discriminator into the pointer's alignment bits. One word instead of two. This is a tagged union at the pointer level — useful for AST nodes, graph edges, or any field with a small number of possible pointer types.

### 12. ScopedHashTable — Lexical Scoping via Push/Pop

```cpp
// Each entry has TWO linked lists: one for its hash bucket, one for its scope.
class ScopedHashTableVal {
  ScopedHashTableVal *NextInScope;  // pop all of these when scope exits
  ScopedHashTableVal *NextForKey;   // normal hash collision chain
  K Key;
  V Val;
};
// Usage: push a scope, insert shadowed bindings, pop scope → all bindings removed in O(1).
```

**Steal this:** When you need variable shadowing (compilers, template engines, config overlays), use a hash table where each scope is a linked list of inserted entries. Entering a scope = push; leaving = pop all entries in that scope. No copying the entire table per scope. The dual-list trick gives O(1) insert, O(1) lookup, and O(entries-in-scope) cleanup.

### 13. LLVM_DEBUG — Zero-Cost Debug Output

```cpp
// In release builds: compiles to NOTHING. Not even a branch.
// In debug builds: one global bool check (almost always false).
#ifdef NDEBUG
#define LLVM_DEBUG(X) do {} while (false)
#else
#define LLVM_DEBUG(X) DEBUG_WITH_TYPE(DEBUG_TYPE, X)
#endif

// Usage — the stream expression is never evaluated in release:
LLVM_DEBUG(dbgs() << "Processing: " << BB->getName() << "\n");
```

**Steal this:** Wrap debug-only output in a macro that compiles to nothing in release. The key insight: the *entire expression* (including string formatting and function calls) is eliminated by the preprocessor. In languages without macros, use a `if (DEBUG)` constant that the compiler can dead-code-eliminate, or a logger with a compile-time level.

### 14. Statistic — Self-Registering Performance Counters

```cpp
// Declare a counter — it auto-registers itself globally.
STATISTIC(NumInstructionsKilled, "Number of instructions eliminated");

// Increment it anywhere — lock-free atomic add.
++NumInstructionsKilled;

// At shutdown: all counters are printed automatically.
// Output: 42 gcse - Number of instructions eliminated
```

**Steal this:** Embed counters directly in your transforms/optimizers/handlers. Use a global registry so they're automatically reported. This costs almost nothing at runtime (one atomic increment) but gives you a complete performance profile for free. Every language can do this — Python `Counter`, Go `expvar`, Java `Micrometer`. The key is making it as easy as `++counter` so developers actually use it.

### 15. TypeSwitch — Functional Pattern Matching

```cpp
// Chain type checks — first match wins, no fall-through.
TypeSwitch<Operation*>(op)
  .Case<ConstantOp>([](auto op) { return foldConstant(op); })
  .Case<AddOp>([](auto op) { return foldAdd(op); })
  .Case<MulOp>([](auto op) { return foldMul(op); })
  .Default([](Operation *op) { return failure(); });
```

**Steal this:** Replace cascading `if (auto *x = dyn_cast<A>(v)) ... else if (auto *y = dyn_cast<B>(v))` with a fluent API that chains cases. Once a case matches, subsequent cases are skipped (just a boolean check). This is C++'s answer to Rust's `match` or Haskell's pattern matching — cleaner, harder to get wrong, and the `.Default()` case makes exhaustiveness explicit.

### 16. StringMap — Tail-Allocated Keys for Cache Locality

```cpp
// Each entry stores key string IMMEDIATELY AFTER the value in memory.
// One allocation per entry, not two (key + value).
class StringMapEntry : public StringMapEntryBase {
  ValueTy second;              // the value
  // char KeyData[KeyLength];  // key bytes follow in memory (tail-allocated)

  const char *getKeyData() const {
    return reinterpret_cast<const char *>(this + 1);  // pointer past the struct
  }
};
```

**Steal this:** When your map keys are variable-length strings, allocate the key data right after the entry struct. One `malloc` per entry instead of two. The key and value are adjacent in cache. This technique works anywhere: C, Rust, Go (via unsafe), even in managed languages with byte arrays. The pattern is: `malloc(sizeof(Entry) + keyLen)`, then store the key at `(char*)(entry + 1)`.

### 17. ManagedStatic — Lazy Globals with Deterministic Shutdown

```cpp
// Lazy-initialized global. Constructed on first access, not at startup.
// Destroyed in reverse order during llvm_shutdown().
static ManagedStatic<PassRegistry> PassRegistryObj;

// Thread-safe first-access pattern:
C &operator*() {
  void *Tmp = Ptr.load(std::memory_order_acquire);
  if (!Tmp) RegisterManagedStatic(Creator, Deleter);
  return *static_cast<C *>(Ptr.load(std::memory_order_relaxed));
}
```

**Steal this:** Global singletons with lazy initialization avoid the "static initialization order fiasco" (globals in different files constructing in unpredictable order). The acquire/relaxed memory ordering pattern makes the fast path (already initialized) nearly free. The shutdown registry ensures deterministic destruction — no leaks, no use-after-free. Apply this anywhere you have global registries or caches.

### 18. FormatVariadic — Type-Safe Printf

```cpp
// Type-safe, extensible formatting. No format string / argument type mismatch.
std::string S = formatv("{0} has {1} uses", V->getName(), V->getNumUses());

// Custom types just implement format_provider:
template <> struct format_provider<MyType> {
  static void format(const MyType &V, raw_ostream &OS, StringRef Style) {
    OS << V.toString();
  }
};
```

**Steal this:** Build a formatting system where the format string references arguments by index (`{0}`, `{1}`) and each type provides its own formatter. No `%d`/`%s` mismatch bugs. No runtime crashes from wrong argument counts. This is the same idea as Python's `f-strings`, Rust's `format!()`, and C#'s string interpolation — but in C++ without language support.

---

## Ways of Thinking — Applicable to Any Language

These aren't C++ tricks. They're **design principles** extracted from how LLVM is architected. They work in Python, Go, Rust, Java, TypeScript — anywhere.

### 19. Data Structures First, Functions Second

> *"Show me your data structures, and I won't usually need your code."* — Fred Brooks (paraphrased)

**LLVM example:** The entire IR is defined by `Value → User → Instruction` (see `llvm/IR/Value.h`). Once you understand these three structs and their linked-list relationships, every optimization pass becomes obvious — it's just walking and rewriting a graph.

**Apply it:** Before writing any function, draw your data structures. If the struct is right, the code writes itself. If you're struggling with an algorithm, you probably have the wrong data layout.

### 20. Make Illegal States Unrepresentable

**LLVM example:** Type IDs are an `enum TypeID` — you cannot construct a `Type` with an invalid ID. `Error` is move-only — you cannot accidentally copy and ignore it. `PointerIntPair` uses `static_assert` to reject types whose alignment doesn't provide enough free bits.

**Apply it:** Use enums instead of strings for states. Use the type system to reject bad inputs at compile time. Make constructors private; expose factory methods that validate. Every runtime `assert` is a confession that the type system could have prevented the bug.

### 21. Phase-Based Lifetimes — Group Objects by When They Die

**LLVM example:** All IR nodes for a function are allocated from a `BumpPtrAllocator` and freed together when the function is done. Instructions live inside BasicBlocks; BasicBlocks live inside Functions. Lifetime = containment hierarchy.

**Apply it:** Don't scatter allocations across the heap. Group objects by phase: "request objects", "compilation objects", "frame objects." Allocate them together, free them together. This simplifies ownership, eliminates use-after-free, and enables arena allocation in any language.

### 22. Non-Owning References as Default API Boundaries

**LLVM example:** `replaceAllUsesWith(Value *V)` takes a raw pointer. `StringRef` is a non-owning view. `ArrayRef<T>` is a non-owning span. APIs never take `unique_ptr` or `shared_ptr` unless they're genuinely acquiring ownership.

**Apply it:** Functions that *read* data should take the simplest possible reference — a pointer, a slice, a view. Don't force callers to wrap things in smart pointers or copy into containers. Ownership is the caller's problem. This makes APIs composable and avoids unnecessary allocations.

### 23. Indirection Enables Global Substitution (RAUW)

**LLVM example:** Every `Value` has a linked list of `Use` objects. `replaceAllUsesWith(NewValue)` walks the list and updates every use in O(n). No search. No "find and replace." The indirection (Use objects between producers and consumers) makes this trivial.

**Apply it:** When you need to swap an implementation everywhere (rename a variable, redirect a service, update a config value), add a level of indirection. Maintain a list of "who references this." Updating the indirection updates everyone. This is why dependency injection, service locators, and reactive state systems work.

### 24. Intern Common Values to Deduplicate

**LLVM example:** `LLVMContextImpl` stores types in DenseMaps keyed by structure. `ConstantInt::get(Type, 42)` returns the *same pointer* every time. The `FoldingSet` hashes an object's contents and returns the existing instance if one matches.

**Apply it:** When you create many structurally identical objects (AST nodes, config keys, database query plans), cache them by content hash. Return the existing instance instead of a new allocation. In Python: `functools.lru_cache`. In Go: `sync.Map`. In Java: `String.intern()`. The key: equality by content, identity by pointer.

### 25. Composable Pipelines of Small Transforms

**LLVM example:** The pass manager runs a sequence of small passes (`instcombine`, `gvn`, `loop-vectorize`). Each pass returns `PreservedAnalyses` declaring what's still valid. The manager skips recomputation of preserved analyses. Passes can be reordered, removed, or added via a text string: `-passes='instcombine,gvn'`.

**Apply it:** Don't build one giant function that does everything. Build tiny transforms, each doing one thing. Chain them. Have each transform declare what it changed so downstream steps can skip redundant work. Unix pipes, middleware stacks, and ETL pipelines all use this pattern.

### 26. Lazy Computation — Don't Compute Until Asked

**LLVM example:** `Function::hasLazyArguments()` — arguments aren't materialized from bitcode until someone calls `getArg(i)`. `AnalysisManager` only runs an analysis when a pass requests it. `Twine` doesn't allocate a string until you call `.str()`.

**Apply it:** Default to lazy. Compute on first access, cache the result. In Python: `@property` + `@lru_cache`. In Go: `sync.Once`. In Rust: `OnceCell`. If 80% of callers never need the value, you've saved 80% of the work. The only exception: when latency spikes matter more than throughput.

### 27. Declarative Descriptions Over Imperative Code

**LLVM example:** Target instruction sets are defined in `.td` files (TableGen), not C++. A single line like `def ADD : I<"add", (outs GPR:$rd), (ins GPR:$rs1, GPR:$rs2)>` generates hundreds of lines of C++ for encoding, decoding, scheduling, and selection.

**Apply it:** When you have many similar things (API routes, database migrations, CLI commands, UI forms), describe them in data (YAML, JSON, a DSL) and generate the boilerplate. Changes become a one-line edit to the description, not a hunt through implementation code. Schema-driven development beats copy-paste-modify.

### 28. Stable Intermediate Representations Decouple Producers from Consumers

**LLVM example:** LLVM IR is the contract. Clang doesn't know about x86. The x86 backend doesn't know about C++. They communicate through IR. Adding a new language = write a frontend that emits IR. Adding a new CPU = write a backend that consumes IR. M frontends × N backends = M+N work, not M×N.

**Apply it:** Whenever you have M producers and N consumers, define a canonical intermediate format. API gateway → canonical event → N processors. Compiler frontend → AST/IR → backends. Import formats → internal model → export formats. The IR is the force multiplier. Without it, every new producer must know about every consumer.

---

*For deeper exploration, see the full analysis in the [.claude-study/](./README.md) directory.*
