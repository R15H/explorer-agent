# The Use-Def Chain — LLVM's Bidirectional SSA Graph

**Source:** `include/llvm/IR/Use.h`, lines 29–106
**Category:** abstraction
**Difficulty:** intermediate

## Context

In SSA-based compilers, every value is defined once and used many times. The question "who uses this value?" comes up constantly during optimization. LLVM implements this with a compact, intrusive linked list that enables O(1) insertion/removal and O(n) traversal of all uses.

The `Use` class is the edge in the def-use graph. It connects a `Value` (the definition) to a `User` (the consumer).

## The Code

From `include/llvm/IR/Use.h`, lines 35–106:

```cpp
class Use {
public:
  Use(const Use &U) = delete;  // Non-copyable

  operator Value *() const { return Val; }
  Value *get() const { return Val; }

  User *getUser() const { return Parent; };

  Use *getNext() const { return Next; }
  unsigned getOperandNo() const;

private:
  Value *Val = nullptr;     // The Value being used
  Use *Next = nullptr;      // Next Use in this Value's use list
  Use **Prev = nullptr;     // Pointer to previous node's Next pointer
  User *Parent = nullptr;   // The User that contains this Use

  void addToList(Use **List) {
    Next = *List;
    if (Next)
      Next->Prev = &Next;
    Prev = List;
    *Prev = this;
  }

  void removeFromList() {
    if (Prev) {
      *Prev = Next;
      if (Next) {
        Next->Prev = Prev;
        Next = nullptr;
      }
      Prev = nullptr;
    }
  }
};
```

## What Makes This Noteworthy

1. **Pointer-to-pointer trick for O(1) removal.** The `Prev` field is not a `Use*` — it's a `Use**`. It points to the `Next` pointer of the previous node (or the `UseList` head pointer in the `Value`). This eliminates the need to special-case removal of the first element.

   ```
   Value::UseList ──► Use_A ──► Use_B ──► Use_C ──► nullptr
        │              │          │          │
        └──Prev of A  └─Prev of B └─Prev of C
        (points to     (points to   (points to
         UseList)       A.Next)      B.Next)
   ```

   To remove `Use_B`:
   ```
   *B.Prev = B.Next;    // A.Next = C
   C.Prev = B.Prev;     // C.Prev = &A.Next
   ```
   No branch for "am I the head?" — the `Prev` pointer abstracts that away.

2. **Non-copyable but movable.** Uses are intrusive — they embed list pointers. Copying would corrupt the list. This is enforced at compile time with `delete`.

3. **Implicit conversion to Value*.** `operator Value*()` means you can use a `Use` anywhere a `Value*` is expected. Combined with the `simplify_type` trait, this means `isa<>`, `cast<>`, and `dyn_cast<>` work transparently on `Use` objects.

4. **Enables RAUW (Replace All Uses With).** The fundamental IR transformation:
   ```cpp
   // Replace %old with %new everywhere
   OldValue->replaceAllUsesWith(NewValue);
   ```
   This walks `OldValue`'s use list and updates each `Use` to point to `NewValue`, moving it to `NewValue`'s use list. O(n) in uses, no allocation.

5. **Zero overhead per unused value.** If a `Value` has no uses, `UseList` is just a null pointer. No sentinel, no empty container.

## Key Takeaways

- The pointer-to-pointer (`T**`) trick for intrusive lists eliminates head-node special cases. Applicable to any intrusive linked list.
- Intrusive data structures avoid separate allocations for nodes and enable O(1) removal when you have a reference to the node.
- Making edges (Use) first-class objects rather than just storing a vector of operands enables efficient bidirectional traversal.
- The `operator Value*()` conversion makes the indirection invisible to client code.

## Related

- [Value.h](../../deep-dives/ir-core.md) — the `UseList` head pointer lives here
- [ilist](ilist.md) — another intrusive list used for Instructions in BasicBlocks
