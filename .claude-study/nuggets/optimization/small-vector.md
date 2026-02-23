# SmallVector — Inline Storage Optimization

**Source:** `include/llvm/ADT/SmallVector.h`, lines 46–100+
**Category:** optimization
**Difficulty:** approachable

## Context

Vectors are everywhere in compilers. But most vectors are small — a function typically has a handful of arguments, a basic block has a few predecessors, an instruction has 2-3 operands. Standard `std::vector` always heap-allocates, even for a vector of 1 element. LLVM's `SmallVector<T, N>` stores up to `N` elements inline (on the stack or in the containing object), falling back to heap allocation only when the vector exceeds `N`.

## The Code

From `include/llvm/ADT/SmallVector.h`, the base class (lines 54–57):

```cpp
template <class Size_T> class SmallVectorBase {
protected:
  void *BeginX;
  Size_T Size = 0, Capacity;
  // ...
};
```

The storage layout (conceptual):

```cpp
template <typename T, unsigned N>
class SmallVector : public SmallVectorImpl<T> {
  // Inline storage for N elements, union'd to get alignment right
  alignas(T) char InlineElts[N * sizeof(T)];
};
```

The growth check:

```cpp
bool isSmall() const {
  return BeginX == getFirstEl();  // Points to inline storage?
}
```

When `BeginX` points to the inline array, the vector is "small" (no heap allocation). When it grows beyond `N`, a heap buffer is allocated and `BeginX` is updated to point to it.

## What Makes This Noteworthy

1. **Zero heap allocations for the common case.** Most compiler data structures have a known typical size. `SmallVector<Value*, 8>` means: "usually 8 or fewer values, occasionally more." The first 8 are free (stack allocation).

2. **Same API as std::vector.** `push_back`, `pop_back`, `begin`/`end`, `operator[]`, `resize`, `reserve` — all work exactly as expected. It's a drop-in replacement.

3. **Size type optimization.** The `Size_T` template parameter on `SmallVectorBase` allows using `uint32_t` for most vectors (saving 8 bytes per vector on 64-bit) while using `uint64_t` for `SmallVector<char>` which may buffer gigabytes of bitcode.

4. **POD optimization.** For trivially copyable types, `SmallVector` uses `memcpy`/`memmove` instead of element-by-element copy/move. The `grow_pod()` method handles reallocation with a single `memcpy`.

5. **Recommended default `N`.** LLVM's coding style recommends `SmallVector<T>` (no explicit `N`) which defaults to a calculated value that makes the total SmallVector size approximately 64 bytes (one cache line). This is almost always a reasonable default.

## Key Takeaways

- Inline/small buffer optimization is one of the most impactful performance patterns for collections that are usually small.
- The same technique applies to strings (`SmallString`), sets (`SmallPtrSet`, `SmallDenseSet`), and other containers.
- Check `isSmall()` to determine if the buffer is inline — useful for understanding allocation behavior.
- When in doubt about `N`, use the default or benchmark. Too large wastes stack space; too small defeats the purpose.

## Related

- [BumpPtrAllocator](bump-ptr-allocator.md) — complementary allocation optimization
- `SmallString<N>` — `SmallVector<char, N>` with string methods
- `SmallPtrSet<T, N>` — small set of pointers with inline storage
- `SmallDenseMap<K, V, N>` — small hash map with inline storage
