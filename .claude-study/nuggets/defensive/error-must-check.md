# Error — Mandatory Checking at Runtime

**Source:** `include/llvm/Support/Error.h`, lines 88–100+
**Category:** defensive
**Difficulty:** intermediate

## Context

Ignoring error return values is one of the most common sources of bugs in C/C++ code. LLVM's `Error` class makes this impossible: if you create an `Error` value and don't check it before it's destroyed, the program terminates with a diagnostic. This is the "checked exception" pattern implemented in C++ without language support.

## The Code

From `include/llvm/Support/Error.h`, lines 88–100 (the class documentation):

```cpp
/// Lightweight error class with error context and mandatory checking.
///
/// Instances of this class wrap a ErrorInfoBase pointer. Failure states
/// are represented by setting the pointer to a ErrorInfoBase subclass
/// instance containing information describing the failure. Success is
/// represented by a null pointer value.
///
/// Instances of Error also contains a 'Checked' flag, which must be set
/// before the destructor is called, otherwise the destructor will trigger a
/// runtime error. This enforces at runtime the requirement that all Error
/// instances be checked or returned to the caller.
```

The destructor (conceptual):

```cpp
~Error() {
  if (!Checked) {
    // In debug builds: abort with a clear diagnostic
    dbgs() << "Program aborted due to an unhandled Error:\n";
    logAllUnhandledErrors(...);
    abort();
  }
}
```

Usage pattern:

```cpp
// Creating an error
Error makeError() {
  return make_error<StringError>("something went wrong",
                                  inconvertibleErrorCode());
}

// Handling an error — MUST do one of these
void caller() {
  Error E = makeError();

  // Option 1: Check with handleErrors
  handleAllErrors(std::move(E), [](const StringError &SE) {
    errs() << SE.getMessage() << "\n";
  });

  // Option 2: Convert to bool (marks as checked)
  if (E) {
    consumeError(std::move(E));
    return;
  }

  // Option 3: Propagate to caller
  return E;  // moves the unchecked Error upward
}
```

The companion class `Expected<T>`:

```cpp
Expected<int> parseNumber(StringRef S) {
  int N;
  if (S.getAsInteger(10, N))
    return make_error<StringError>("not a number", inconvertibleErrorCode());
  return N;
}

// Caller must check:
auto Result = parseNumber("42");
if (!Result) {
  consumeError(Result.takeError());
  return;
}
int N = *Result;  // Safe — we checked
```

## What Makes This Noteworthy

1. **Compiler-enforced error handling.** If you ignore an `Error`, your program crashes with a clear message at the point of destruction. This catches bugs during development, not in production.

2. **Move-only semantics.** `Error` is non-copyable. You must either handle it, propagate it (return), or explicitly consume it. There's no way to accidentally lose an error by copying.

3. **Typed error info.** The `ErrorInfo<T>` template lets you create specific error types:
   ```cpp
   class FileNotFoundError : public ErrorInfo<FileNotFoundError> {
     static char ID;
     std::string Path;
   public:
     void log(raw_ostream &OS) const override { OS << Path << " not found"; }
   };
   ```
   Handlers can match on specific error types, similar to catch blocks.

4. **Expected<T> — Result type.** The combination of a value or an error. Equivalent to Rust's `Result<T, E>` or Haskell's `Either`. If the `Expected<T>` holds an error and you try to access the value without checking, it crashes.

5. **Success is zero-cost.** When there's no error, `Error` is just a null pointer and a boolean flag. The `Checked` flag is only needed in debug builds.

## Key Takeaways

- Use checked types (like `Error` / `Expected<T>`) to enforce error handling at the API level, not through documentation.
- Move semantics prevent accidental error duplication or loss.
- Typed errors with pattern-matching handlers are more composable than error codes or string messages.
- This pattern is applicable to any C++ codebase — the key insight is using the destructor as a "did you check?" enforcer.

## Related

- `ErrorOr<T>` — older variant using `std::error_code` (being phased out in favor of `Expected<T>`)
- Rust's `#[must_use]` and `Result<T, E>` — same concept, with compiler support
- [LLVM Programmer's Manual — Error handling](https://llvm.org/docs/ProgrammersManual.html#error-handling)
