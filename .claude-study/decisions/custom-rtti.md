# Decision: Custom RTTI Instead of C++ dynamic_cast

**Area:** Core infrastructure (`llvm/Support/Casting.h`)
**Evidence:** `llvm/docs/CodingStandards.rst`, `llvm/docs/HowToSetUpLLVMStyleRTTI.rst`

## The Decision

LLVM compiles with `-fno-rtti` (C++ RTTI disabled) and implements its own type identification system using `isa<>`, `cast<>`, and `dyn_cast<>` templates backed by `static classof()` methods.

## The Alternatives

1. **C++ RTTI (`dynamic_cast`, `typeid`)** — the standard language feature.
2. **Virtual `getKind()` method** — a single virtual method returning an enum. Used by some projects.
3. **LLVM's `classof()` pattern** — static method + stored discriminator, no virtual dispatch.

## Why This Way

From LLVM's Coding Standards:

1. **Binary size.** C++ RTTI generates type information for every class with virtual methods. In a project with thousands of classes (LLVM has many thousands), this adds significant binary bloat. Disabling RTTI with `-fno-rtti` reduces binary size.

2. **Performance.** `dynamic_cast` is slower than a simple integer comparison. In a compiler that does millions of type checks per compilation, this adds up. LLVM's `classof()` method typically compiles down to a single comparison instruction.

3. **Flexibility.** The `classof()` pattern works for arbitrary classification — not just the C++ class hierarchy. You can have `isa<TerminatorInst>(I)` check an opcode range rather than a single class identity. This is impossible with `dynamic_cast`.

4. **No virtual method required.** `classof()` is static. The base class just needs a discriminator field (like `Value::SubclassID`). Classes can participate in the RTTI system without having any virtual methods.

5. **Composability with smart pointers.** The `simplify_type` trait allows `isa<>`, `cast<>`, and `dyn_cast<>` to work transparently with `unique_ptr<T>`, `T*`, `const T*`, etc.

## Consequences

**Positive:**
- Smaller binaries (~5-10% reduction from disabling RTTI)
- Faster type checks (integer comparison vs vtable lookup + type info traversal)
- More flexible classification (range checks, multi-level hierarchies)
- Works with `-fno-rtti` and `-fno-exceptions` builds

**Negative:**
- Every new class needs a `classof()` method and potentially a `SubclassID` entry
- Maintenance burden: discriminator enums must stay in sync with the class hierarchy
- Cannot use standard `dynamic_cast` anywhere in the codebase (it's globally disabled)
- New contributors must learn LLVM-specific casting idioms

## Trail

- Implementation: `include/llvm/Support/Casting.h`
- Tutorial: `docs/HowToSetUpLLVMStyleRTTI.rst`
- Coding standards rationale: `docs/CodingStandards.rst`
- Value discriminator: `include/llvm/IR/Value.h` (lines 76-77, `SubclassID` field)
