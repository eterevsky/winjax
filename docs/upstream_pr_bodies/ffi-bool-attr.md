## Symptom

On MSVC-compatible compilers (MSVC, clang-cl), every CUB-rewritten sort or top_k crashes in `strlen(NULL)`: `EstimateCubSortScratchSize` calls `attrs.Insert("descending", false)` (`xla/backends/gpu/transforms/estimate_cub_sort_scratch_size.cc`), and the call dies before the custom call is even built. In jax terms: `jnp.sort` of large arrays and `approx_top_k` crash the process.

## Root cause

`CallFrameBuilder::AttributesBuilder` has a `const char*` convenience overload of `Insert`. On MSVC-compatible compilers the boolean literals `true`/`false` convert to a null pointer via a legacy extension (a standard-sanctioned conversion for `false`, extended by MSVC to both literals), and that pointer conversion wins overload resolution against the user-defined conversion to `Attribute`. So `Insert(name, false)` selects the `const char*` overload with a null pointer and crashes constructing `std::string`.

## Fix

Add an exact-match `bool` overload so genuine bool attributes become PRED scalars on every compiler. The overload is constrained to exactly `bool` with `enable_if`: a plain `Insert(std::string, bool)` overload would also capture other integral types (the standard integral-to-bool conversion outranks the user-defined conversion to `Attribute`), silently turning int64 attributes such as `batch_size` into PRED scalars — this variant was verified to preserve all existing non-bool attribute types.

Found while porting XLA to native Windows.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
