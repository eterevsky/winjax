# CCCL patch series (applied by configure.py)

XLA's CUB/Thrust usage compiles CCCL headers with clang in CUDA mode against
the MSVC STL. Two families of upstream CCCL bugs break that combination; the
patches here fix them in a **copy** of the toolkit's CCCL headers.

`configure.py` copies `<CUDA toolkit>/include/cccl` to
`toolchains/cccl_patched/` and applies these patches with `git apply -p1`.
The `@cuda_cccl` override repo and the compiler wrapper's `-I` then point at
the patched copy; the pristine toolkit headers are never modified.

- `0001-string-view-host-device-deduction-guides.patch` —
  `cuda/std/string_view`'s deduction guides from `::std::basic_string(_view)`
  are declared `_CCCL_HOST`, which poisons the whole deduction-guide set in
  device compilation (clang rejects host-only guides referenced implicitly
  from device code via the `cub.cuh` umbrella). Declare them
  `_CCCL_HOST_DEVICE`.
- `0002-cccl-throw-std-qualification.patch` — `_CCCL_THROW(std::..., ...)`
  in 5 headers expands inside namespaces where unqualified `std` resolves to
  `cuda::std`; qualify as `::std::` (5 files: `cuda/__driver/driver_api.h`,
  `cuda/__mdspan/dlpack_to_mdspan.h`, `cuda/__mdspan/mdspan_to_dlpack.h`,
  `cuda/__memory_resource/allocation_alignment.h`,
  `cuda/__tma/make_tma_descriptor.h`).

Diffed against CUDA toolkit 13.3 (13.3.73). On a newer 13.x toolkit a hunk
may drift; if `git apply` fails, re-derive the same one-token changes by hand
(they are mechanical) and regenerate the patch.
