load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

licenses(["restricted"])  # NVIDIA proprietary license

cc_import(
    name = "cupti_shared_library",
    hdrs = [":headers"],
    interface_library = "lib/cupti.lib",
    system_provided = 1,
)

# Static CUPTI libraries are not shipped on Windows; targets kept name-only.
cc_library(
    name = "cupti_static_library",
)

cc_library(
    name = "nvperf_host_static_library",
)

cc_library(
    name = "cupti",
    deps = [":cupti_shared_library"],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "header_list",
    srcs = glob([
        "include/Openacc/**",
        "include/Openmp/**",
        "include/cuda_stdint.h",
        "include/cupti.h",
        "include/cupti_activity.h",
        "include/cupti_activity_deprecated.h",
        "include/cupti_callbacks.h",
        "include/cupti_checkpoint.h",
        "include/cupti_driver_cbid.h",
        "include/cupti_events.h",
        "include/cupti_metrics.h",
        "include/cupti_nvtx_cbid.h",
        "include/cupti_pcsampling.h",
        "include/cupti_pcsampling_util.h",
        "include/cupti_profiler_target.h",
        "include/cupti_result.h",
        "include/cupti_runtime_cbid.h",
        "include/cupti_sass_metrics.h",
        "include/cupti_target.h",
        "include/cupti_version.h",
        "include/generated_cudaGL_meta.h",
        "include/generated_cudaVDPAU_meta.h",
        "include/generated_cuda_gl_interop_meta.h",
        "include/generated_cuda_meta.h",
        "include/generated_cuda_runtime_api_meta.h",
        "include/generated_cuda_vdpau_interop_meta.h",
        "include/generated_cudart_removed_meta.h",
        "include/generated_nvtx_meta.h",
        "include/nvperf_common.h",
        "include/nvperf_cuda_host.h",
        "include/nvperf_host.h",
        "include/nvperf_target.h",
    ]) + [
        # Inlined if_version_equal_or_greater_than branches: CUPTI 2026.2.1
        # is newer than all thresholds (2024.0, 2024.3, 2024.3.2).
        "include/cupti_common.h",
        "include/cupti_pmsampling.h",
        "include/cupti_profiler_host.h",
        "include/cupti_range_profiler.h",
    ],
    visibility = ["@local_config_cuda//cuda:__pkg__"],
)

cc_library(
    name = "headers",
    hdrs = [":header_list"],
    include_prefix = "third_party/gpus/cuda/extras/CUPTI/include",
    includes = ["include/"],
    strip_include_prefix = "include",
    visibility = ["@local_config_cuda//cuda:__pkg__"],
)
