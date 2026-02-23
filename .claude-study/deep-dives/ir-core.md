# Deep Dive: The LLVM IR Core

The IR is the heart of LLVM. Every frontend emits it, every optimization pass transforms it, and every backend consumes it. Understanding the IR is understanding LLVM.

---

## The Class Hierarchy

The IR class hierarchy is rooted at `Value`. Every computed result — instructions, function arguments, constants, global variables — is a `Value`. This uniformity is what makes the SSA use-def chain work.

```
Value                           (include/llvm/IR/Value.h)
├── Argument                    (include/llvm/IR/Argument.h)
├── BasicBlock                  (include/llvm/IR/BasicBlock.h)
├── MetadataAsValue
├── InlineAsm
└── User                        (include/llvm/IR/User.h)
    ├── Constant                (include/llvm/IR/Constant.h)
    │   ├── GlobalValue         (include/llvm/IR/GlobalValue.h)
    │   │   ├── GlobalObject
    │   │   │   ├── Function    (include/llvm/IR/Function.h)
    │   │   │   └── GlobalVariable (include/llvm/IR/GlobalVariable.h)
    │   │   ├── GlobalAlias
    │   │   └── GlobalIFunc
    │   ├── ConstantInt         (include/llvm/IR/Constants.h)
    │   ├── ConstantFP
    │   ├── ConstantArray
    │   ├── ConstantStruct
    │   ├── ConstantVector
    │   ├── ConstantDataSequential
    │   ├── ConstantExpr
    │   ├── UndefValue
    │   ├── PoisonValue
    │   └── ConstantPointerNull
    └── Instruction             (include/llvm/IR/Instruction.h)
        ├── BinaryOperator
        ├── UnaryOperator
        ├── CmpInst (ICmpInst, FCmpInst)
        ├── CastInst (TruncInst, ZExtInst, SExtInst, ...)
        ├── LoadInst
        ├── StoreInst
        ├── AllocaInst
        ├── GetElementPtrInst
        ├── PHINode
        ├── SelectInst
        ├── CallInst / InvokeInst / CallBrInst
        ├── BranchInst / SwitchInst / IndirectBrInst
        ├── ReturnInst / UnreachableInst
        ├── ExtractValueInst / InsertValueInst
        ├── ExtractElementInst / InsertElementInst / ShuffleVectorInst
        ├── AtomicRMWInst / AtomicCmpXchgInst / FenceInst
        ├── LandingPadInst / ResumeInst / CatchPadInst / ...
        └── FreezeInst
```

## The Value / User / Use Triangle

This is the most important design pattern in LLVM IR. Three classes work together:

### Value (`include/llvm/IR/Value.h`)

Every `Value` has:
- A **Type** (`Value::getType()`)
- A **name** (optional, for readability — `%foo`, `@global`)
- A **use list** — a singly-linked list of `Use` objects pointing back to all Users

Key fields from `Value.h`, lines 76–100:
```cpp
class Value {
  const unsigned char SubclassID;   // For isa/dyn_cast (LLVM RTTI)
  unsigned char HasValueHandle : 1;
protected:
  unsigned char SubclassOptionalData : 7;  // Optimization hints
private:
  unsigned short SubclassData;             // Subclass-specific storage
protected:
  unsigned NumUserOperands;                // Operand count (for User subclasses)
  // ...
  Use *UseList;                            // Head of the use list
};
```

### User (`include/llvm/IR/User.h`)

A `User` is a `Value` that has operands (references to other `Value`s). Each operand is a `Use` object. `User` provides `getOperand(i)`, `setOperand(i, V)`, and `getNumOperands()`.

### Use (`include/llvm/IR/Use.h`)

A `Use` is the **edge** in the SSA def-use graph. It has four pointers:
```cpp
class Use {
  Value *Val = nullptr;     // The Value being used (the definition)
  Use *Next = nullptr;      // Next Use in the Value's use list
  Use **Prev = nullptr;     // Pointer to previous Use's Next pointer
  User *Parent = nullptr;   // The User that contains this Use
};
```

This is an intrusive doubly-linked list (using `Prev` as a pointer-to-pointer for O(1) removal).

### How They Connect

```
   Function @foo:                       Instruction: %r = add i32 %x, %y
   ┌─────────────┐
   │   Value @foo │                    ┌────────────────────┐
   │   UseList ──────► Use (in call)   │  User: add         │
   └─────────────┘                     │  Operand[0] ──► %x │ (Use edge)
                                       │  Operand[1] ──► %y │ (Use edge)
                                       │  Result: %r        │ (Value)
                                       └────────────────────┘
```

When pass code does `%x->replaceAllUsesWith(%z)`, LLVM walks `%x`'s use list and updates every `Use` to point to `%z` instead. This is O(n) in the number of uses — and because the list is intrusive, there's no searching or allocation involved.

---

## The Module Container

`Module` (`include/llvm/IR/Module.h`) is the top-level container. It owns:

- **Function list** — `Module::getFunctionList()` returns an `ilist<Function>`
- **Global variable list** — `Module::getGlobalList()` returns an `ilist<GlobalVariable>`
- **Alias list** — `Module::getAliasList()`
- **Named metadata** — `Module::getNamedMetadataList()`
- **Data layout string** — describes target endianness, pointer sizes, alignment
- **Target triple** — e.g., `x86_64-unknown-linux-gnu`

A Module maps to a single translation unit (one `.c` or `.cpp` file). The LTO (Link-Time Optimization) pipeline can merge multiple Modules into one.

---

## The Type System

LLVM types are uniquified per `LLVMContext`. Two structurally identical types are always pointer-equal.

**Primitive types:** `void`, `half`, `bfloat`, `float`, `double`, `fp128`, `x86_fp80`, `ppc_fp128`, `label`, `metadata`, `token`, `ptr`

**Derived types:**
- `IntegerType` — `iN` for any bit width N (1 to 2^23)
- `FunctionType` — `i32 (i32, ptr)` (return type + parameter types)
- `StructType` — `{i32, float, ptr}` (named or literal)
- `ArrayType` — `[10 x i32]`
- `VectorType` — `<4 x float>` (fixed) or `<vscale x 4 x float>` (scalable)
- `PointerType` — `ptr` (opaque pointers; typed pointers are legacy)

Opaque pointers (`ptr` without a pointee type) are now the default. This was a major simplification — previously `i32*` and `float*` were different types, which complicated pointer casts.

**Files:**
- `include/llvm/IR/Type.h` — base `Type` class
- `include/llvm/IR/DerivedTypes.h` — derived type subclasses

---

## The Instruction Set

LLVM IR instructions are organized into categories:

### Terminator Instructions
End a basic block. Determine control flow.
- `ret`, `br`, `switch`, `indirectbr`, `invoke`, `callbr`, `resume`, `catchswitch`, `catchret`, `cleanupret`, `unreachable`

### Binary Operations
Two operands, one result. Operate on integers or floats.
- Integer: `add`, `sub`, `mul`, `udiv`, `sdiv`, `urem`, `srem`
- Float: `fadd`, `fsub`, `fmul`, `fdiv`, `frem`
- Bitwise: `shl`, `lshr`, `ashr`, `and`, `or`, `xor`

### Memory Operations
- `alloca` — allocate stack memory
- `load` — read from memory
- `store` — write to memory
- `fence` — memory ordering fence
- `cmpxchg` — atomic compare-and-exchange
- `atomicrmw` — atomic read-modify-write
- `getelementptr` (GEP) — compute element addresses in aggregates

### Cast Operations
- `trunc`, `zext`, `sext` — integer width changes
- `fptrunc`, `fpext` — float precision changes
- `fptoui`, `fptosi`, `uitofp`, `sitofp` — float/int conversions
- `ptrtoint`, `inttoptr` — pointer/integer conversions
- `bitcast` — reinterpret bits (now rarely needed with opaque pointers)
- `addrspacecast` — pointer address space conversion

### Other Operations
- `icmp`, `fcmp` — integer/float comparison
- `phi` — SSA phi node
- `select` — conditional value selection (ternary operator)
- `call` — function call
- `va_arg` — variadic argument access
- `extractelement`, `insertelement`, `shufflevector` — vector operations
- `extractvalue`, `insertvalue` — aggregate (struct/array) operations
- `freeze` — convert poison/undef to a fixed (but arbitrary) value

---

## IRBuilder — The Construction API

`IRBuilder` (`include/llvm/IR/IRBuilder.h`) is the primary API for programmatically creating IR:

```cpp
LLVMContext Context;
Module M("my_module", Context);
FunctionType *FT = FunctionType::get(Type::getInt32Ty(Context),
                                      {Type::getInt32Ty(Context)}, false);
Function *F = Function::Create(FT, Function::ExternalLinkage, "double_it", M);

BasicBlock *BB = BasicBlock::Create(Context, "entry", F);
IRBuilder<> Builder(BB);

Value *Arg = F->getArg(0);
Value *Two = ConstantInt::get(Type::getInt32Ty(Context), 2);
Value *Result = Builder.CreateMul(Arg, Two, "result");
Builder.CreateRet(Result);
```

Produces:
```llvm
define i32 @double_it(i32 %0) {
entry:
  %result = mul i32 %0, 2
  ret i32 %result
}
```

---

## The Verifier

`Verifier.cpp` (`lib/IR/Verifier.cpp`, ~8,300 lines) is the largest single file in the IR library. It checks structural correctness:
- Every instruction dominates all its uses
- Phi nodes are at the beginning of basic blocks
- Phi nodes have entries for every predecessor
- Terminators are at the end of basic blocks
- Types match between instructions and their operands
- Function signatures match call sites
- Intrinsic calls have correct argument types

The verifier runs after every pass in debug builds (`-verify-each`).

---

## Metadata and Debug Info

LLVM IR carries metadata alongside instructions. Metadata does not affect program semantics but provides information to passes:

- **!dbg** — source location (file, line, column) for debug info
- **!tbaa** — type-based alias analysis information
- **!prof** — branch probability weights (from PGO)
- **!range** — value range constraints
- **!invariant.load** — marks loads that always return the same value

Debug info uses the DWARF model, represented as IR metadata nodes (`DISubprogram`, `DILocalVariable`, `DILocation`, etc.). The `DebugInfoMetadata.h` header defines these.

**Files:**
- `include/llvm/IR/Metadata.h`
- `include/llvm/IR/DebugInfoMetadata.h`
- `lib/IR/DebugInfo.cpp`
