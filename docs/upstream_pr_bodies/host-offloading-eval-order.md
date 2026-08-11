## Symptom

On Windows (MSVC ABI), every compilation that uses host offloading (e.g. jax `compute_on('device_host')`, exercised by jax's `memories_test`) crashes with an access violation (0xC0000005) inside `HostOffloadingNanoRtExecutable::LoadFromProto`.

## Root cause

The constructor call at the end of `LoadFromProto` (`xla/core/host_offloading/host_offloading_nanort_executable.cc`) evaluates `executable->program_shape()` and `std::move(executable)` in the same argument list:

```cpp
return absl::WrapUnique(new HostOffloadingNanoRtExecutable(
    hlo_module_proto.name(),
    executable->program_shape() ? *executable->program_shape() : program_shape,
    std::move(alias_config), std::move(executable), ...));
```

The constructor takes the executable as a by-value `unique_ptr`, so that parameter is constructed during argument evaluation, and the order is unspecified. On the MSVC ABI (right-to-left) the move happens first, and `program_shape()` is then called through a null pointer. clang constant-folds the dereference into an absolute load at the member offset, so it reliably crashes rather than "usually working".

## Fix

Hoist the program-shape selection into a local before the constructor call. Same bug class as the `CommonPjRtClient::LinearizeIntoImpl` evaluation-order fix.

Found while porting XLA to native Windows; any toolchain that evaluates function arguments right-to-left is affected.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
