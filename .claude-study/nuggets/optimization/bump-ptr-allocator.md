# BumpPtrAllocator — Arena Allocation for Compilers

**Source:** `include/llvm/Support/Allocator.h`, lines 45–100+
**Category:** optimization
**Difficulty:** approachable

## Context

Compilers allocate and deallocate millions of small objects (AST nodes, IR instructions, symbol table entries). Using `malloc`/`free` for each would be prohibitively slow due to per-allocation overhead and heap fragmentation. LLVM uses `BumpPtrAllocator` — an arena allocator that trades individual deallocation for extreme allocation speed.

## The Code

From `include/llvm/Support/Allocator.h`, lines 62–66 (template declaration):

```cpp
template <typename AllocatorT = MallocAllocator, size_t SlabSize = 4096,
          size_t SizeThreshold = SlabSize, size_t GrowthDelay = 128>
class BumpPtrAllocatorImpl
    : public AllocatorBase<BumpPtrAllocatorImpl<AllocatorT, SlabSize,
                                                SizeThreshold, GrowthDelay>> {
```

The allocation fast path (conceptually):

```cpp
LLVM_ATTRIBUTE_RETURNS_NONNULL void *Allocate(size_t Size, Align Alignment) {
  // Bump CurPtr to the right alignment
  char *Ptr = (char *)alignAddr(CurPtr, Alignment);
  // Check if it fits in the current slab
  if (Ptr + Size <= End) {
    CurPtr = Ptr + Size;
    return Ptr;
  }
  // Slow path: allocate a new slab
  return AllocateSlow(Size, Alignment);
}
```

The key data members:

```cpp
char *CurPtr = nullptr;           // Next free byte in current slab
char *End = nullptr;              // End of current slab
SmallVector<void *, 4> Slabs;     // All allocated slabs
SmallVector<std::pair<void *, size_t>, 0> CustomSizedSlabs; // Oversized allocs
size_t BytesAllocated = 0;        // Total bytes allocated
```

## What Makes This Noteworthy

1. **Allocation is two pointer comparisons and an add.** The fast path: align `CurPtr`, check against `End`, bump `CurPtr`. No free list traversal, no metadata bookkeeping, no locking (single-threaded use assumed).

2. **Slab growth strategy.** Starts with 4KB slabs. After `GrowthDelay` (128) slabs, doubles the slab size. This balances memory waste (small slabs for small compilations) with allocation efficiency (large slabs reduce slab-switching overhead for large compilations).

3. **Oversized allocations go to their own slab.** Anything larger than `SizeThreshold` (default = `SlabSize`) gets its own `malloc`'d block, tracked separately in `CustomSizedSlabs`. This prevents a single large allocation from wasting most of a slab.

4. **Deallocation is free.** Individual objects cannot be freed. The entire arena is freed at once when the `BumpPtrAllocator` is destroyed. This is safe because compiler objects have phase-based lifetimes — all the IR for a function is allocated during construction and freed together after code generation.

5. **BumpPtrAllocator is composable.** It implements the LLVM "Allocator" concept, so it can be used as the backing allocator for `StringMap`, `FoldingSet`, and other LLVM containers.

## Key Takeaways

- Arena/bump-pointer allocation is the gold standard for allocation-heavy, phase-based workloads.
- The pattern: maintain a pointer to free space, bump it forward on allocation, free everything at once.
- The slab design avoids pre-committing large contiguous virtual address space while still providing bump-pointer semantics.
- Applicable to any system where objects share a common lifetime (request handlers, game frames, compiler passes).

## Related

- [SmallVector](small-vector.md) — another allocation optimization (inline storage)
- LLVM's `BumpPtrList` — a list that allocates its nodes from a BumpPtrAllocator
