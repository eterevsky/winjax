## Symptom

On Windows (MSVC ABI), every host-to-device transfer through `CommonPjRtClient::BufferFromHostBuffer` crashes with an access violation in `tsl::RunWhenReady` — the very first `jax.device_put`/`jnp.array` on a GPU device dies.

## Root cause

In `CommonPjRtClient::LinearizeIntoImpl` (`xla/pjrt/common_pjrt_client.cc`), the dependency list for `async_work_runner()->ExecuteWhenReady` is built with `linearized.CopyRCRef()` in the same argument list as a lambda that captures `linearized` by move:

```cpp
async_work_runner()->ExecuteWhenReady(
    {linearized.CopyRCRef()},
    [this, linearized = std::move(linearized), ...]() mutable { ... });
```

C++ argument evaluation order is unspecified. On the MSVC ABI arguments are evaluated right-to-left, so the lambda object (and with it the move of `linearized`) is constructed first, and `CopyRCRef()` then runs on a moved-from `AsyncValueRef`, producing a null dependency.

## Fix

Hoist the `CopyRCRef()` into a local before the call, so the dependency is taken while `linearized` is still valid. No behavior change on toolchains that happened to evaluate left-to-right.

Found while porting XLA to native Windows; any toolchain that evaluates function arguments right-to-left is affected.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
