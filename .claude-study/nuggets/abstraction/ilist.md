# ilist — Intrusive Doubly-Linked List

**Source:** `include/llvm/ADT/ilist.h`, `include/llvm/ADT/simple_ilist.h`
**Category:** abstraction
**Difficulty:** intermediate

## Context

LLVM needs to frequently insert, remove, and splice sequences of IR nodes (Instructions within BasicBlocks, BasicBlocks within Functions). Standard `std::list` allocates separate heap nodes, which is wasteful — the IR objects already exist. LLVM's `ilist` embeds the prev/next pointers directly in the listed objects, enabling O(1) insert/remove/splice with zero extra allocations.

## The Code

From `include/llvm/ADT/ilist.h`, lines 1–22 (header comment):

```cpp
/// This file defines classes to implement an intrusive doubly linked list class
/// (i.e. each node of the list must contain a next and previous field for the
/// list.
///
/// The ilist class itself should be a plug in replacement for list. This list
/// replacement does not provide a constant time size() method, so be careful to
/// use empty() when you really want to know if it's empty.
///
/// The ilist class is implemented as a circular list. The list itself contains
/// a sentinel node, whose Next points at begin() and whose Prev points at
/// rbegin(). The sentinel node itself serves as end() and rend().
```

The trait callbacks (lines 65–76):

```cpp
template <typename NodeTy> struct ilist_callback_traits {
  void addNodeToList(NodeTy *) {}
  void removeNodeFromList(NodeTy *) {}

  template <class Iterator>
  void transferNodesFromList(ilist_callback_traits &OldList,
                             Iterator /*first*/, Iterator /*last*/) {
    (void)OldList;
  }
};
```

Usage in LLVM IR — BasicBlock contains an ilist of Instructions:

```cpp
// From include/llvm/IR/BasicBlock.h (simplified)
class BasicBlock : public Value, public ilist_node_with_parent<BasicBlock, Function> {
  InstListType InstList;  // ilist<Instruction>
public:
  iterator begin() { return InstList.begin(); }
  iterator end()   { return InstList.end(); }

  // O(1) splice: move instructions from another block
  void splice(iterator Where, BasicBlock *Other, iterator First, iterator Last) {
    InstList.splice(Where, Other->InstList, First, Last);
  }
};
```

## What Makes This Noteworthy

1. **Zero-allocation insert/remove.** Since the list pointers are embedded in the nodes themselves, inserting or removing a node requires only pointer manipulation — no `new`/`delete`.

2. **O(1) splice.** Moving a contiguous range of instructions from one basic block to another is a constant-time pointer swap. This is essential for transformations like loop unrolling, code motion, and basic block merging.

3. **Circular sentinel design.** The list uses a sentinel node (embedded in the list object itself) as both `end()` and `rend()`. This eliminates null-pointer checks in traversal — `begin()` is always a valid dereferenceable iterator or equal to `end()`.

4. **Callback traits.** The `ilist_callback_traits` template provides hooks for when nodes are added or removed. LLVM uses this to update parent pointers — when an Instruction is added to a BasicBlock, the Instruction's parent is set automatically.

5. **No constant-time size().** Deliberately. Maintaining a size counter would add overhead to every insert/remove/splice. LLVM code uses `empty()` (O(1)) and avoids `size()` when possible. This is a conscious tradeoff: splice performance is more important than constant-time size.

6. **LLVM's IR structure depends on it.** The entire IR containment hierarchy uses ilist:
   - `Module` → `ilist<Function>`
   - `Function` → `ilist<BasicBlock>`
   - `BasicBlock` → `ilist<Instruction>`

## Key Takeaways

- Intrusive containers eliminate per-node heap allocation. When objects already exist in memory, embed the list pointers in them.
- The circular sentinel pattern eliminates null checks and head/tail special cases.
- If you frequently splice ranges of elements between lists, intrusive lists are the right data structure.
- Giving up constant-time `size()` is often the right tradeoff for O(1) splice.

## Related

- [Use-Def Chain](use-def-chain.md) — another intrusive list pattern (single-linked, with pointer-to-pointer trick)
- `simple_ilist` — the lower-level building block that `ilist` is built on (no ownership semantics)
- `iplist` — ilist variant with ownership (calls `deleteNode` on removal)
