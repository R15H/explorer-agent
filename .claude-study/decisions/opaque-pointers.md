# Decision: Opaque Pointers

**Area:** LLVM IR Type System
**Evidence:** [llvm-dev mailing list (2015)](https://lists.llvm.org/pipermail/llvm-dev/2015-February/081822.html), `llvm/docs/OpaquePointers.rst`

## The Decision

Remove pointee types from LLVM IR pointers. Replace all typed pointers (`i32*`, `float*`, `%struct.Foo*`) with a single opaque pointer type: `ptr`.

Instructions that need type information now carry it explicitly:
```llvm
; Before (typed pointers):
load i64* %p
getelementptr %struct.Foo, %struct.Foo* %p, i32 0, i32 1

; After (opaque pointers):
load i64, ptr %p
getelementptr %struct.Foo, ptr %p, i32 0, i32 1
```

## The Alternatives

1. **Keep typed pointers** — the status quo for 20+ years. Every pointer carries its pointee type.
2. **Gradual deprecation with compatibility mode** — what was actually done. Both forms coexisted during the transition, with opaque pointers becoming the default in LLVM 15 and typed pointers removed in LLVM 17.

## Why This Way

From `llvm/docs/OpaquePointers.rst`:

> *"LLVM IR pointers can be cast back and forth between pointers with different pointee types. The pointee type does not necessarily represent the actual underlying type in memory. In other words, the pointee type carries no real semantics."*

The core problems with typed pointers:

1. **No-op bitcasts everywhere.** Converting `i32*` to `i8*` produces a `bitcast` instruction that does nothing at the machine level but clutters the IR, wastes memory, and increases compile time.

2. **Easy to miss `stripPointerCasts()`.** When traversing def-use chains, every pass had to remember to look through bitcasts to find the real underlying pointer. Forgetting this caused subtle missed optimizations.

3. **Address space bugs.** Frontends (especially Clang) sometimes incorrectly bitcast pointers between address spaces, losing critical information for GPU and embedded backends.

4. **Optimization algorithms ignore pointee types anyway.** SROA, GVN, and alias analysis reason about memory offsets, not pointer types. The type system was not helping optimizations.

5. **Historical precedent.** LLVM previously removed signed/unsigned integer type distinctions (`uint` vs `int` → just `i32` with operation flags). Same pattern: types that carry no semantic weight create unnecessary complexity.

The proposal was first made in **2015** and took approximately 8 years to fully complete (LLVM 17, released 2023). The gradual migration involved:
- Adding the `ptr` type alongside typed pointers
- Migrating all passes to handle both forms
- Making opaque pointers the default
- Removing typed pointer support entirely

## Consequences

**Positive:**
- Fewer IR instructions (no no-op bitcasts)
- Simpler pass development (no need to `stripPointerCasts()` everywhere)
- Reduced memory usage and compile time
- Eliminated a class of address space bugs
- Simpler IR serialization and parsing

**Negative:**
- Massive migration effort across the entire LLVM codebase and all downstream users
- Loss of type-level bug detection in frontends (frontends now rely on their own type checking)
- Some debugging convenience lost (can't see pointed-to type at a glance in IR dumps)

## Trail

- Original proposal: [llvm-dev mailing list, February 2015](https://lists.llvm.org/pipermail/llvm-dev/2015-February/081822.html)
- Migration tracking: `llvm/docs/OpaquePointers.rst`
- Default in LLVM 15, typed pointers removed in LLVM 17
