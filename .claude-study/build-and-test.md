# Building and Testing LLVM

---

## Prerequisites

| Package | Version | Notes |
|---------|---------|-------|
| CMake | >= 3.20.0 | Build system generator |
| C++ Compiler | GCC >= 7.4 or Clang >= 5.0 | Must support C++17 |
| Python | >= 3.8 | For `lit` test runner and scripts |
| Ninja | Latest | Recommended build tool (faster than Make) |
| zlib | >= 1.2.3.4 | Optional, for compression support |

**Disk space:** ~1-3 GB for LLVM-only Debug build, ~15-20 GB for full LLVM+Clang Debug build. Release builds are much smaller.

**RAM:** At least 8 GB recommended. Linking is memory-intensive; use `-DLLVM_PARALLEL_LINK_JOBS=2` on constrained machines.

---

## Quick Start — LLVM Only (Debug)

```bash
# Clone
git clone --depth 1 https://github.com/llvm/llvm-project.git
cd llvm-project

# Configure
cmake -S llvm -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Debug \
  -DLLVM_ENABLE_ASSERTIONS=ON

# Build
ninja -C build

# Test
ninja -C build check-llvm
```

## Quick Start — LLVM + Clang (Release)

```bash
cmake -S llvm -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLVM_ENABLE_PROJECTS="clang;lld" \
  -DLLVM_ENABLE_ASSERTIONS=ON

ninja -C build
ninja -C build check-all
```

---

## Key CMake Options

### Build Type

```bash
-DCMAKE_BUILD_TYPE=<type>
```
- `Debug` — full debug info, no optimization, assertions ON. Slow but best for development.
- `Release` — full optimization, no debug info, assertions OFF.
- `RelWithDebInfo` — optimization + debug info. Good balance for debugging optimized code.
- `MinSizeRel` — optimize for size.

### Subprojects

```bash
-DLLVM_ENABLE_PROJECTS="clang;lld;lldb;mlir;polly;clang-tools-extra"
```

Semicolon-separated list. Available: `clang`, `clang-tools-extra`, `lld`, `lldb`, `mlir`, `polly`, `bolt`, `flang`, `cross-project-tests`.

### Runtime Libraries

```bash
-DLLVM_ENABLE_RUNTIMES="compiler-rt;libcxx;libcxxabi;libunwind;openmp"
```

Runtime libraries are built separately using the just-built compiler.

### Target Backends

```bash
-DLLVM_TARGETS_TO_BUILD="X86;AArch64;RISCV"
```

Build only specific target backends. Default is `all`. Use `host` for just the host architecture. Reducing targets significantly speeds up build times.

### Useful Developer Options

```bash
# Use LLD for faster linking
-DLLVM_USE_LINKER=lld

# Limit parallel link jobs (links are memory-hungry)
-DLLVM_PARALLEL_LINK_JOBS=2

# Build shared libraries (faster linking during development)
-DBUILD_SHARED_LIBS=ON

# Enable expensive checks (slow, but catches more bugs)
-DLLVM_ENABLE_EXPENSIVE_CHECKS=ON

# Build with sanitizers
-DLLVM_USE_SANITIZER="Address;Undefined"

# Use ccache for faster rebuilds
-DCMAKE_C_COMPILER_LAUNCHER=ccache
-DCMAKE_CXX_COMPILER_LAUNCHER=ccache

# Build only specific tools
-DLLVM_BUILD_TOOLS=ON
-DLLVM_TOOL_<TOOL>_BUILD=OFF  # Disable specific tools
```

---

## CMake Presets

LLVM ships CMake presets in `llvm/CMakePresets.json`:

```bash
# List available presets
cmake --list-presets -S llvm

# Use a preset
cmake --preset <preset-name> -S llvm
```

---

## Running Tests

### Regression Tests (lit)

```bash
# All LLVM tests
ninja -C build check-llvm

# All Clang tests
ninja -C build check-clang

# All tests across all enabled subprojects
ninja -C build check-all

# Run a specific test file
./build/bin/llvm-lit llvm/test/Transforms/InstCombine/add.ll

# Run a specific test directory
./build/bin/llvm-lit llvm/test/Transforms/InstCombine/

# Run with verbose output
./build/bin/llvm-lit -v llvm/test/Transforms/InstCombine/add.ll

# Run with specific number of threads
./build/bin/llvm-lit -j4 llvm/test/
```

**How lit tests work:**
1. Each `.ll` or `.c` test file contains `RUN:` lines specifying commands to execute
2. The test typically runs an LLVM tool (opt, llc, clang) on the input
3. Output is piped through `FileCheck` which verifies expected patterns
4. `CHECK:`, `CHECK-NEXT:`, `CHECK-NOT:`, `CHECK-DAG:` directives define patterns

Example test structure:
```llvm
; RUN: opt -passes=instcombine -S < %s | FileCheck %s

define i32 @test_add_zero(i32 %x) {
; CHECK-LABEL: @test_add_zero(
; CHECK-NEXT:    ret i32 %x
  %r = add i32 %x, 0
  ret i32 %r
}
```

### Unit Tests (Google Test)

```bash
# All unit tests
ninja -C build check-llvm-unit

# Run specific unit test binary
./build/unittests/IR/IRTests
./build/unittests/ADT/ADTTests

# Run specific test case
./build/unittests/IR/IRTests --gtest_filter="*ValueTest*"
```

---

## Development Workflow

### Building a Single Tool

```bash
# Build only opt
ninja -C build opt

# Build only llc
ninja -C build llc

# Build only clang
ninja -C build clang
```

### Regenerating TableGen Files

```bash
# Rebuild all TableGen outputs
ninja -C build llvm-tblgen
ninja -C build <target>CommonTableGen  # e.g., X86CommonTableGen
```

### Running a Single Pass

```bash
# Run instcombine on a .ll file
./build/bin/opt -passes=instcombine -S input.ll -o output.ll

# Run the full O2 pipeline
./build/bin/opt -passes='default<O2>' -S input.ll

# Run a specific pass and see what changed
./build/bin/opt -passes=instcombine -S input.ll -print-changed

# Lower IR to assembly
./build/bin/llc input.ll -o output.s

# Lower IR to object code
./build/bin/llc -filetype=obj input.ll -o output.o
```

### Debugging

```bash
# Print IR after each pass
./build/bin/opt -passes='default<O2>' -print-after-all -S input.ll

# Print IR only when it changes
./build/bin/opt -passes='default<O2>' -print-changed -S input.ll

# Get optimization remarks
./build/bin/opt -passes='default<O2>' -pass-remarks=.* -S input.ll

# Verify IR after each pass (slow but catches bugs)
./build/bin/opt -passes='default<O2>' -verify-each -S input.ll

# Use bugpoint to reduce a failing test case
./build/bin/bugpoint input.bc -run-passes=<failing-pass>

# Use llvm-reduce for more targeted reduction
./build/bin/llvm-reduce --test=<test-script> input.ll
```

---

## Useful Development Targets

| Target | Description |
|--------|-------------|
| `ninja -C build` | Build everything |
| `ninja -C build opt` | Build just the opt tool |
| `ninja -C build check-llvm` | Run LLVM regression tests |
| `ninja -C build check-clang` | Run Clang tests |
| `ninja -C build check-all` | Run all tests |
| `ninja -C build check-llvm-unit` | Run LLVM unit tests |
| `ninja -C build clang-format` | Format source code |
| `ninja -C build docs-llvm-html` | Build LLVM HTML docs |
| `ninja -C build install` | Install to CMAKE_INSTALL_PREFIX |
