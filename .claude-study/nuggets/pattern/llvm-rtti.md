# LLVM Custom RTTI: isa<>, cast<>, dyn_cast<>

**Source:** `include/llvm/Support/Casting.h`
**Category:** pattern
**Difficulty:** intermediate

## Context

LLVM compiles with `-fno-rtti` (C++ RTTI disabled) for performance and binary size reasons. But a compiler needs type checking everywhere — "is this Value an Instruction?", "is this Instruction a BranchInst?". LLVM solves this with a custom RTTI system that is faster than `dynamic_cast` and works without virtual table overhead.

This system is used **thousands of times** across the codebase. Understanding it is prerequisite to reading any LLVM code.

## The Code

From `Casting.h`, lines 63–71 — the core dispatch mechanism:

```cpp
// The core of the implementation of isa<X> is here; To and From should be
// the names of classes.  This template can be specialized to customize the
// implementation of isa<> without rewriting it from scratch.
template <typename To, typename From, typename Enabler = void> struct isa_impl {
  static inline bool doit(const From &Val) { return To::classof(&Val); }
};

// Always allow upcasts, and perform no dynamic check for them.
template <typename To, typename From>
struct isa_impl<To, From, std::enable_if_t<std::is_base_of_v<To, From>>> {
  static inline bool doit(const From &) { return true; }
};
```

And the `classof` pattern in a concrete class (from `include/llvm/IR/Instructions.h`):

```cpp
class BranchInst : public Instruction {
public:
  static bool classof(const Instruction *I) {
    return I->getOpcode() == Instruction::Br;
  }
  static bool classof(const Value *V) {
    return isa<Instruction>(V) && classof(cast<Instruction>(V));
  }
};
```

Usage throughout the codebase:

```cpp
if (auto *BI = dyn_cast<BranchInst>(TerminatorInst)) {
  // BI is a BranchInst*, guaranteed non-null
  if (BI->isConditional()) {
    // ...
  }
}
```

## What Makes This Noteworthy

1. **No virtual dispatch.** The `classof` method is a `static` function that checks a stored discriminator field (`SubclassID` in `Value`, or `Opcode` in `Instruction`). This is a simple integer comparison — no vtable lookup, no pointer indirection.

2. **Compile-time upcast optimization.** The `enable_if` specialization means that `isa<Value>(someInstruction)` is always `true` and compiles to nothing. Upcasts in the type hierarchy are free.

3. **Extensible via `classof`.** Any class can participate in the RTTI system by implementing a `static bool classof(const Base *)` method. No need to modify the base class.

4. **Safe by default.** `isa<>` and `cast<>` assert on null pointers. `dyn_cast<>` returns nullptr on failure. `dyn_cast_if_present<>` (formerly `dyn_cast_or_null`) handles nullable inputs.

5. **Works with smart pointers.** The `simplify_type` trait and `isa_impl_cl` specializations handle `unique_ptr`, raw pointers, const pointers, etc.

A naive approach would use `dynamic_cast` or a virtual `getKind()` method. LLVM's approach is faster (no vtable lookup), more flexible (any class can opt in), and works without RTTI runtime support.

## Key Takeaways

- Store a type discriminator field in the base class and check it in derived classes via `static classof()`.
- Use template specialization to optimize away redundant type checks (upcasts).
- This pattern works for any class hierarchy and is widely applicable outside LLVM.
- The `dyn_cast<>` idiom — check and cast in one step — is cleaner than separate `if` + `static_cast`.

## Related

- [Value.h](../../deep-dives/ir-core.md) — `SubclassID` field that makes this work
- [LLVM Coding Standards](https://llvm.org/docs/CodingStandards.html#use-of-rtti-and-dynamic-cast) — rationale for avoiding C++ RTTI
- [LLVM Programmer's Manual — isa/cast](https://llvm.org/docs/ProgrammersManual.html#the-isa-cast-and-dyn-cast-templates) — official documentation
