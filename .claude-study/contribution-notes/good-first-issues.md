# Good First Issues for LLVM Contributors

Areas where a newcomer can make meaningful contributions with manageable scope.

---

## 1. Test Coverage Improvements

**Where:** `llvm/test/`, `llvm/unittests/`
**What:** Add missing test cases for edge conditions, especially for optimization passes.
**Why accessible:** Tests are self-contained `.ll` files with `RUN:` + `FileCheck` directives. You learn the tool workflow without modifying C++.

**Approach:**
- Pick an optimization pass (e.g., `instcombine`, `simplifycfg`)
- Read a few existing tests in `llvm/test/Transforms/<Pass>/`
- Look at the pass source code for code paths not covered by existing tests
- Write a `.ll` test file exercising that path

---

## 2. Documentation Improvements

**Where:** `llvm/docs/`
**What:** Fix outdated documentation, add examples, improve clarity.
**Why accessible:** RST files, no C++ changes needed. Many docs reference obsolete features (typed pointers, legacy pass manager).

**Specific opportunities:**
- Update pass descriptions that still reference the Legacy Pass Manager
- Add more examples to the Language Reference (`LangRef.rst`)
- Improve the `WritingAnLLVMPass.rst` tutorial with New Pass Manager examples
- Fix broken links and outdated command-line examples

---

## 3. Trivial Code Cleanups

**Where:** Various
**What:** Remove dead code, fix compiler warnings, modernize C++ usage.

**Specific patterns to look for:**
- `auto *X = dyn_cast<Y>(V); if (X) {` → `if (auto *X = dyn_cast<Y>(V)) {`
- Uses of `unsigned` for boolean values → `bool`
- Raw pointer ownership patterns that could use `std::unique_ptr`
- `std::string` parameters that could be `StringRef`

---

## 4. LLVM Coding Standards Alignment

**Where:** Throughout the codebase
**What:** Fix deviations from the [LLVM Coding Standards](https://llvm.org/docs/CodingStandards.html).

**Examples:**
- Functions using `camelCase` instead of `PascalCase` (LLVM convention for function names)
- Missing `[[nodiscard]]` on pure query functions
- Comments that don't follow Doxygen format (`///` for documentation, `//` for implementation notes)

---

## 5. GlobalISel Expansion

**Where:** `lib/CodeGen/GlobalISel/`, `lib/Target/*/GISel/`
**What:** Implement missing legalizer rules, combine patterns, or instruction selection patterns for targets using GlobalISel.
**Why accessible:** GlobalISel is actively developed and has many clearly defined TODOs. The `LegalizerHelper.cpp` file alone has **47 TODO/FIXME** comments.

**Specific files with many TODOs:**
- `lib/CodeGen/GlobalISel/LegalizerHelper.cpp` — 47 TODOs
- `lib/CodeGen/GlobalISel/CombinerHelper.cpp` — 29 TODOs
- `lib/CodeGen/GlobalISel/IRTranslator.cpp` — 22 TODOs
- `lib/CodeGen/GlobalISel/GISelValueTracking.cpp` — 18 TODOs

---

## 6. InstCombine Pattern Additions

**Where:** `lib/Transforms/InstCombine/`
**What:** Add new algebraic simplification patterns.
**Why accessible:** Each pattern is relatively self-contained — match an instruction pattern, replace with a simpler equivalent. Well-established testing infrastructure.

**How to find candidates:**
- Look at [Alive2](https://alive2.llvm.org/) for verified transformation ideas
- Check LLVM Bugzilla/GitHub issues tagged "instcombine"
- Examine missed optimizations in `opt -passes=instcombine` output

---

## 7. Improving Error Messages

**Where:** `lib/AsmParser/`, `lib/Bitcode/`, `lib/IR/Verifier.cpp`
**What:** Improve diagnostic messages for malformed IR, better error recovery.
**Why accessible:** Each improvement is localized and testable.

---

## How to Submit a Contribution

1. Fork the [llvm-project repository](https://github.com/llvm/llvm-project)
2. Create a branch for your change
3. Make changes and add tests
4. Run relevant tests: `ninja -C build check-llvm` (or `check-clang`, etc.)
5. Submit a pull request on GitHub
6. Follow the [Contributing to LLVM](https://llvm.org/docs/Contributing.html) guide

**Important conventions:**
- Commit messages should be descriptive and reference any related issues
- PRs need approval from a code owner (see `Maintainers.md` in each subproject)
- All changes must include tests
- Follow the [LLVM Coding Standards](https://llvm.org/docs/CodingStandards.html)
