# Copyright 2018 The Bazel Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This becomes the BUILD file for @local_config_cc// under Windows.
# winjax: rendered from toolchains/templates/local_config_cc/BUILD.tpl by
# configure.py — do not edit the generated copy by hand.

load("@rules_cc//cc:defs.bzl", "cc_toolchain", "cc_toolchain_suite", "cc_library")
load(":windows_cc_toolchain_config.bzl", "cc_toolchain_config")
load(":armeabi_cc_toolchain_config.bzl", "armeabi_cc_toolchain_config")

package(default_visibility = ["//visibility:public"])

cc_library(name = "empty_lib")

# Label flag for extra libraries to be linked into every binary.
# TODO(bazel-team): Support passing flag multiple times to build a list.
label_flag(
    name = "link_extra_libs",
    build_setting_default = ":empty_lib",
)

# The final extra library to be linked into every binary target. This collects
# the above flag, but may also include more libraries depending on config.
cc_library(
    name = "link_extra_lib",
    deps = [
        ":link_extra_libs",
    ],
)

cc_library(
    name = "malloc",
)

filegroup(
    name = "empty",
    srcs = [],
)

filegroup(
    name = "mingw_compiler_files",
    srcs = [":builtin_include_directory_paths_mingw"]
)

filegroup(
    name = "clangcl_compiler_files",
    srcs = [":builtin_include_directory_paths_clangcl"]
)

filegroup(
    name = "msvc_compiler_files",
    srcs = [":builtin_include_directory_paths_msvc"]
)

# Hardcoded toolchain, legacy behaviour.
cc_toolchain_suite(
    name = "toolchain",
    toolchains = {
        "armeabi-v7a|compiler": ":cc-compiler-armeabi-v7a",
        "x64_windows|msvc-cl": ":cc-compiler-x64_windows",
        "x64_x86_windows|msvc-cl": ":cc-compiler-x64_x86_windows",
        "x64_arm_windows|msvc-cl": ":cc-compiler-x64_arm_windows",
        "x64_arm64_windows|msvc-cl": ":cc-compiler-arm64_windows",
        "arm64_windows|msvc-cl": ":cc-compiler-arm64_windows",
        "x64_windows|msys-gcc": ":cc-compiler-x64_windows_msys",
        "x64_windows|mingw-gcc": ":cc-compiler-x64_windows_mingw",
        "x64_windows|clang-cl": ":cc-compiler-x64_windows-clang-cl",
        "x64_windows_msys": ":cc-compiler-x64_windows_msys",
        "x64_windows": ":cc-compiler-x64_windows",
        "x64_x86_windows": ":cc-compiler-x64_x86_windows",
        "x64_arm_windows": ":cc-compiler-x64_arm_windows",
        "x64_arm64_windows": ":cc-compiler-arm64_windows",
        "arm64_windows": ":cc-compiler-arm64_windows",
        "x64_arm64_windows|clang-cl": ":cc-compiler-arm64_windows-clang-cl",
        "arm64_windows|clang-cl": ":cc-compiler-arm64_windows-clang-cl",
        "armeabi-v7a": ":cc-compiler-armeabi-v7a",
    },
)

cc_toolchain(
    name = "cc-compiler-x64_windows_msys",
    toolchain_identifier = "msys_x64",
    toolchain_config = ":msys_x64",
    all_files = ":empty",
    ar_files = ":empty",
    as_files = ":mingw_compiler_files",
    compiler_files = ":mingw_compiler_files",
    dwp_files = ":empty",
    linker_files = ":empty",
    objcopy_files = ":empty",
    strip_files = ":empty",
    supports_param_files = 1,
)

cc_toolchain_config(
    name = "msys_x64",
    cpu = "x64_windows",
    compiler = "msys-gcc",
    host_system_name = "local",
    target_system_name = "local",
    target_libc = "msys",
    abi_version = "local",
    abi_libc_version = "local",
    cxx_builtin_include_directories = [        "@@MSYS_ROOT_FWD@@/usr/",
        ],
    tool_paths = {"ar": "@@MSYS_ROOT_FWD@@/usr/bin/ar",
        "cpp": "@@MSYS_ROOT_FWD@@/usr/bin/cpp",
        "dwp": "@@MSYS_ROOT_FWD@@/usr/bin/dwp",
        "gcc": "@@MSYS_ROOT_FWD@@/usr/bin/gcc",
        "gcov": "@@MSYS_ROOT_FWD@@/usr/bin/gcov",
        "ld": "@@MSYS_ROOT_FWD@@/usr/bin/ld",
        "nm": "@@MSYS_ROOT_FWD@@/usr/bin/nm",
        "objcopy": "@@MSYS_ROOT_FWD@@/usr/bin/objcopy",
        "objdump": "@@MSYS_ROOT_FWD@@/usr/bin/objdump",
        "strip": "@@MSYS_ROOT_FWD@@/usr/bin/strip"},
    tool_bin_path = "@@MSYS_ROOT_FWD@@/usr/bin",
    dbg_mode_debug_flag = "/DEBUG:FULL",
    fastbuild_mode_debug_flag = "/DEBUG:FASTLINK",
)

toolchain(
    name = "cc-toolchain-x64_windows_msys",
    exec_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:windows",
        "@bazel_tools//tools/cpp:msys",
    ],
    target_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:windows",
    ],
    toolchain = ":cc-compiler-x64_windows_msys",
    toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
)

cc_toolchain(
    name = "cc-compiler-x64_windows_mingw",
    toolchain_identifier = "msys_x64_mingw",
    toolchain_config = ":msys_x64_mingw",
    all_files = ":empty",
    ar_files = ":empty",
    as_files = ":mingw_compiler_files",
    compiler_files = ":mingw_compiler_files",
    dwp_files = ":empty",
    linker_files = ":empty",
    objcopy_files = ":empty",
    strip_files = ":empty",
    supports_param_files = 0,
)

cc_toolchain_config(
    name = "msys_x64_mingw",
    cpu = "x64_windows",
    compiler = "mingw-gcc",
    host_system_name = "local",
    target_system_name = "local",
    target_libc = "mingw",
    abi_version = "local",
    abi_libc_version = "local",
    tool_bin_path = "@@MSYS_ROOT_FWD@@/mingw64/bin",
    cxx_builtin_include_directories = [        "@@MSYS_ROOT_FWD@@/mingw64/",
        ],
    tool_paths = {"ar": "@@MSYS_ROOT_FWD@@/mingw64/bin/ar",
        "cpp": "@@MSYS_ROOT_FWD@@/mingw64/bin/cpp",
        "dwp": "@@MSYS_ROOT_FWD@@/mingw64/bin/dwp",
        "gcc": "@@MSYS_ROOT_FWD@@/mingw64/bin/gcc",
        "gcov": "@@MSYS_ROOT_FWD@@/mingw64/bin/gcov",
        "ld": "@@MSYS_ROOT_FWD@@/mingw64/bin/ld",
        "nm": "@@MSYS_ROOT_FWD@@/mingw64/bin/nm",
        "objcopy": "@@MSYS_ROOT_FWD@@/mingw64/bin/objcopy",
        "objdump": "@@MSYS_ROOT_FWD@@/mingw64/bin/objdump",
        "strip": "@@MSYS_ROOT_FWD@@/mingw64/bin/strip"},
    dbg_mode_debug_flag = "/DEBUG:FULL",
    fastbuild_mode_debug_flag = "/DEBUG:FASTLINK",
)

toolchain(
    name = "cc-toolchain-x64_windows_mingw",
    exec_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:windows",
        "@bazel_tools//tools/cpp:mingw",
    ],
    target_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:windows",
    ],
    toolchain = ":cc-compiler-x64_windows_mingw",
    toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
)

cc_toolchain(
    name = "cc-compiler-x64_windows",
    toolchain_identifier = "msvc_x64",
    toolchain_config = ":msvc_x64",
    all_files = ":empty",
    ar_files = ":empty",
    as_files = ":msvc_compiler_files",
    compiler_files = ":msvc_compiler_files",
    dwp_files = ":empty",
    linker_files = ":empty",
    objcopy_files = ":empty",
    strip_files = ":empty",
    supports_param_files = 1,
)

cc_toolchain_config(
    name = "msvc_x64",
    cpu = "x64_windows",
    compiler = "msvc-cl",
    host_system_name = "local",
    target_system_name = "local",
    target_libc = "msvcrt",
    abi_version = "local",
    abi_libc_version = "local",
    toolchain_identifier = "msvc_x64",
    msvc_env_tmp = "@@MSVC_ENV_TMP_BS@@",
    msvc_env_path = "@@MSVC_ENV_PATH_X64_BS@@",
    msvc_env_include = "@@MSVC_ENV_INCLUDE_X64_BS@@",
    msvc_env_lib = "@@MSVC_ENV_LIB_X64_BS@@",
    msvc_cl_path = "@@MSVC_BIN_X64_FWD@@/cl.exe",
    msvc_ml_path = "@@MSVC_BIN_X64_FWD@@/ml64.exe",
    msvc_link_path = "@@MSVC_BIN_X64_FWD@@/link.exe",
    msvc_lib_path = "@@MSVC_BIN_X64_FWD@@/lib.exe",
    cxx_builtin_include_directories = [@@MSVC_BUILTIN_DIRS_X64@@],
    tool_paths = {
        "ar": "@@MSVC_BIN_X64_FWD@@/lib.exe",
        "ml": "@@MSVC_BIN_X64_FWD@@/ml64.exe",
        "cpp": "@@MSVC_BIN_X64_FWD@@/cl.exe",
        "gcc": "@@MSVC_BIN_X64_FWD@@/cl.exe",
        "gcov": "wrapper/bin/msvc_nop.bat",
        "ld": "@@MSVC_BIN_X64_FWD@@/link.exe",
        "nm": "wrapper/bin/msvc_nop.bat",
        "objcopy": "wrapper/bin/msvc_nop.bat",
        "objdump": "wrapper/bin/msvc_nop.bat",
        "strip": "wrapper/bin/msvc_nop.bat",
    },
    archiver_flags = ["/MACHINE:X64"],
    default_link_flags = ["/MACHINE:X64"],
    dbg_mode_debug_flag = "/DEBUG:FULL",
    fastbuild_mode_debug_flag = "/DEBUG:FASTLINK",
    supports_parse_showincludes = True,
)

toolchain(
    name = "cc-toolchain-x64_windows",
    exec_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:windows",
    ],
    target_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:windows",
    ],
    toolchain = ":cc-compiler-x64_windows",
    toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
)

cc_toolchain(
    name = "cc-compiler-x64_x86_windows",
    toolchain_identifier = "msvc_x64_x86",
    toolchain_config = ":msvc_x64_x86",
    all_files = ":empty",
    ar_files = ":empty",
    as_files = ":msvc_compiler_files",
    compiler_files = ":msvc_compiler_files",
    dwp_files = ":empty",
    linker_files = ":empty",
    objcopy_files = ":empty",
    strip_files = ":empty",
    supports_param_files = 1,
)

cc_toolchain_config(
    name = "msvc_x64_x86",
    cpu = "x64_windows",
    compiler = "msvc-cl",
    host_system_name = "local",
    target_system_name = "local",
    target_libc = "msvcrt",
    abi_version = "local",
    abi_libc_version = "local",
    toolchain_identifier = "msvc_x64_x86",
    msvc_env_tmp = "@@MSVC_ENV_TMP_BS@@",
    msvc_env_path = "@@MSVC_ENV_PATH_X86_BS@@",
    msvc_env_include = "@@MSVC_ENV_INCLUDE_X86_BS@@",
    msvc_env_lib = "@@MSVC_ENV_LIB_X86_BS@@",
    msvc_cl_path = "@@MSVC_BIN_X86_FWD@@/cl.exe",
    msvc_ml_path = "@@MSVC_BIN_X86_FWD@@/ml.exe",
    msvc_link_path = "@@MSVC_BIN_X86_FWD@@/link.exe",
    msvc_lib_path = "@@MSVC_BIN_X86_FWD@@/lib.exe",
    cxx_builtin_include_directories = [@@MSVC_BUILTIN_DIRS_X86@@],
    tool_paths = {
        "ar": "@@MSVC_BIN_X86_FWD@@/lib.exe",
        "ml": "@@MSVC_BIN_X86_FWD@@/ml.exe",
        "cpp": "@@MSVC_BIN_X86_FWD@@/cl.exe",
        "gcc": "@@MSVC_BIN_X86_FWD@@/cl.exe",
        "gcov": "wrapper/bin/msvc_nop.bat",
        "ld": "@@MSVC_BIN_X86_FWD@@/link.exe",
        "nm": "wrapper/bin/msvc_nop.bat",
        "objcopy": "wrapper/bin/msvc_nop.bat",
        "objdump": "wrapper/bin/msvc_nop.bat",
        "strip": "wrapper/bin/msvc_nop.bat",
    },
    archiver_flags = ["/MACHINE:X86"],
    default_link_flags = ["/MACHINE:X86"],
    dbg_mode_debug_flag = "/DEBUG:FULL",
    fastbuild_mode_debug_flag = "/DEBUG:FASTLINK",
    supports_parse_showincludes = True,
)

toolchain(
    name = "cc-toolchain-x64_x86_windows",
    exec_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:windows",
    ],
    target_compatible_with = [
        "@platforms//cpu:x86_32",
        "@platforms//os:windows",
    ],
    toolchain = ":cc-compiler-x64_x86_windows",
    toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
)

cc_toolchain(
    name = "cc-compiler-x64_arm_windows",
    toolchain_identifier = "msvc_x64_arm",
    toolchain_config = ":msvc_x64_arm",
    all_files = ":empty",
    ar_files = ":empty",
    as_files = ":msvc_compiler_files",
    compiler_files = ":msvc_compiler_files",
    dwp_files = ":empty",
    linker_files = ":empty",
    objcopy_files = ":empty",
    strip_files = ":empty",
    supports_param_files = 1,
)

cc_toolchain_config(
    name = "msvc_x64_arm",
    cpu = "x64_windows",
    compiler = "msvc-cl",
    host_system_name = "local",
    target_system_name = "local",
    target_libc = "msvcrt",
    abi_version = "local",
    abi_libc_version = "local",
    toolchain_identifier = "msvc_x64_arm",
    msvc_env_tmp = "msvc_not_found",
    msvc_env_path = "msvc_not_found",
    msvc_env_include = "msvc_not_found",
    msvc_env_lib = "msvc_not_found",
    msvc_cl_path = "vc_installation_error_arm.bat",
    msvc_ml_path = "vc_installation_error_arm.bat",
    msvc_link_path = "vc_installation_error_arm.bat",
    msvc_lib_path = "vc_installation_error_arm.bat",
    cxx_builtin_include_directories = [],
    tool_paths = {
        "ar": "vc_installation_error_arm.bat",
        "ml": "vc_installation_error_arm.bat",
        "cpp": "vc_installation_error_arm.bat",
        "gcc": "vc_installation_error_arm.bat",
        "gcov": "wrapper/bin/msvc_nop.bat",
        "ld": "vc_installation_error_arm.bat",
        "nm": "wrapper/bin/msvc_nop.bat",
        "objcopy": "wrapper/bin/msvc_nop.bat",
        "objdump": "wrapper/bin/msvc_nop.bat",
        "strip": "wrapper/bin/msvc_nop.bat",
    },
    archiver_flags = ["/MACHINE:ARM"],
    default_link_flags = ["/MACHINE:ARM"],
    dbg_mode_debug_flag = "/DEBUG",
    fastbuild_mode_debug_flag = "/DEBUG",
    supports_parse_showincludes = False,
)

toolchain(
    name = "cc-toolchain-x64_arm_windows",
    exec_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:windows",
    ],
    target_compatible_with = [
        "@platforms//cpu:arm",
        "@platforms//os:windows",
    ],
    toolchain = ":cc-compiler-x64_arm_windows",
    toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
)

cc_toolchain(
    name = "cc-compiler-arm64_windows",
    toolchain_identifier = "msvc_arm64",
    toolchain_config = ":msvc_arm64",
    all_files = ":empty",
    ar_files = ":empty",
    as_files = ":msvc_compiler_files",
    compiler_files = ":msvc_compiler_files",
    dwp_files = ":empty",
    linker_files = ":empty",
    objcopy_files = ":empty",
    strip_files = ":empty",
    supports_param_files = 1,
)

cc_toolchain_config(
    name = "msvc_arm64",
    cpu = "x64_windows",
    compiler = "msvc-cl",
    host_system_name = "local",
    target_system_name = "local",
    target_libc = "msvcrt",
    abi_version = "local",
    abi_libc_version = "local",
    toolchain_identifier = "msvc_arm64",
    msvc_env_tmp = "msvc_not_found",
    msvc_env_path = "msvc_not_found",
    msvc_env_include = "msvc_not_found",
    msvc_env_lib = "msvc_not_found",
    msvc_cl_path = "vc_installation_error_arm64.bat",
    msvc_ml_path = "vc_installation_error_arm64.bat",
    msvc_link_path = "vc_installation_error_arm64.bat",
    msvc_lib_path = "vc_installation_error_arm64.bat",
    cxx_builtin_include_directories = [],
    tool_paths = {
        "ar": "vc_installation_error_arm64.bat",
        "ml": "vc_installation_error_arm64.bat",
        "cpp": "vc_installation_error_arm64.bat",
        "gcc": "vc_installation_error_arm64.bat",
        "gcov": "wrapper/bin/msvc_nop.bat",
        "ld": "vc_installation_error_arm64.bat",
        "nm": "wrapper/bin/msvc_nop.bat",
        "objcopy": "wrapper/bin/msvc_nop.bat",
        "objdump": "wrapper/bin/msvc_nop.bat",
        "strip": "wrapper/bin/msvc_nop.bat",
    },
    archiver_flags = ["/MACHINE:ARM64"],
    default_link_flags = ["/MACHINE:ARM64"],
    dbg_mode_debug_flag = "/DEBUG",
    fastbuild_mode_debug_flag = "/DEBUG",
    supports_parse_showincludes = False,
)

toolchain(
    name = "cc-toolchain-arm64_windows",
    exec_compatible_with = [
        "@platforms//os:windows",
    ],
    target_compatible_with = [
        "@platforms//cpu:arm64",
        "@platforms//os:windows",
    ],
    toolchain = ":cc-compiler-arm64_windows",
    toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
)


cc_toolchain(
    name = "cc-compiler-x64_windows-clang-cl",
    toolchain_identifier = "clang_cl_x64",
    toolchain_config = ":clang_cl_x64",
    all_files = ":empty",
    ar_files = ":empty",
    as_files = ":clangcl_compiler_files",
    compiler_files = ":clangcl_compiler_files",
    dwp_files = ":empty",
    linker_files = ":empty",
    objcopy_files = ":empty",
    strip_files = ":empty",
    supports_param_files = 1,
)

cc_toolchain_config(
    name = "clang_cl_x64",
    cpu = "x64_windows",
    compiler = "clang-cl",
    host_system_name = "local",
    target_system_name = "local",
    target_libc = "msvcrt",
    abi_version = "local",
    abi_libc_version = "local",
    toolchain_identifier = "clang_cl_x64",
    msvc_env_tmp = "@@MSVC_ENV_TMP_BS@@",
    msvc_env_path = "@@MSVC_ENV_PATH_X64_BS@@",
    msvc_env_include = "@@CLANG_CL_ENV_INCLUDE_BS@@",
    msvc_env_lib = "@@CLANG_CL_ENV_LIB_X64_BS@@",
    msvc_cl_path = "@@WINJAX_CL_BAT_FWD@@",
    msvc_ml_path = "@@LLVM_BIN_FWD@@/clang-cl.exe",
    msvc_link_path = "@@LLVM_BIN_FWD@@/lld-link.exe",
    msvc_lib_path = "@@LLVM_BIN_FWD@@/llvm-lib.exe",
    cxx_builtin_include_directories = [@@CLANG_CL_BUILTIN_DIRS@@],
    tool_paths = {
        "ar": "@@LLVM_BIN_FWD@@/llvm-lib.exe",
        "ml": "@@LLVM_BIN_FWD@@/clang-cl.exe",
        "cpp": "@@WINJAX_CL_BAT_FWD@@",
        "gcc": "@@WINJAX_CL_BAT_FWD@@",
        "gcov": "wrapper/bin/msvc_nop.bat",
        "ld": "@@LLVM_BIN_FWD@@/lld-link.exe",
        "nm": "wrapper/bin/msvc_nop.bat",
        "objcopy": "wrapper/bin/msvc_nop.bat",
        "objdump": "wrapper/bin/msvc_nop.bat",
        "strip": "wrapper/bin/msvc_nop.bat",
    },
    archiver_flags = ["/MACHINE:X64"],
    default_link_flags = ["/MACHINE:X64"],
    dbg_mode_debug_flag = "/DEBUG",
    fastbuild_mode_debug_flag = "/DEBUG",
    supports_parse_showincludes = True,
)

toolchain(
    name = "cc-toolchain-x64_windows-clang-cl",
    exec_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:windows",
        "@bazel_tools//tools/cpp:clang-cl",
    ],
    target_compatible_with = [
        "@platforms//cpu:x86_64",
        "@platforms//os:windows",
    ],
    toolchain = ":cc-compiler-x64_windows-clang-cl",
    toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
)

cc_toolchain(
    name = "cc-compiler-arm64_windows-clang-cl",
    toolchain_identifier = "clang_cl_arm64",
    toolchain_config = ":clang_cl_arm64",
    all_files = ":empty",
    ar_files = ":empty",
    as_files = ":clangcl_compiler_files",
    compiler_files = ":clangcl_compiler_files",
    dwp_files = ":empty",
    linker_files = ":empty",
    objcopy_files = ":empty",
    strip_files = ":empty",
    supports_param_files = 1,
)

cc_toolchain_config(
    name = "clang_cl_arm64",
    cpu = "arm64_windows",
    compiler = "clang-cl",
    host_system_name = "local",
    target_system_name = "aarch64-pc-windows-msvc",
    target_libc = "msvcrt",
    abi_version = "local",
    abi_libc_version = "local",
    toolchain_identifier = "clang_cl_arm64",
    msvc_env_tmp = "clang_cl_not_found",
    msvc_env_path = "clang_cl_not_found",
    msvc_env_include = "clang_cl_not_found",
    msvc_env_lib = "clang_cl_not_found",
    msvc_cl_path = "vc_installation_error_arm64.bat",
    msvc_ml_path = "vc_installation_error_arm64.bat",
    msvc_link_path = "vc_installation_error_arm64.bat",
    msvc_lib_path = "vc_installation_error_arm64.bat",
    cxx_builtin_include_directories = [],
    tool_paths = {
        "ar": "vc_installation_error_arm64.bat",
        "ml": "vc_installation_error_arm64.bat",
        "cpp": "vc_installation_error_arm64.bat",
        "gcc": "vc_installation_error_arm64.bat",
        "gcov": "wrapper/bin/msvc_nop.bat",
        "ld": "vc_installation_error_arm64.bat",
        "nm": "wrapper/bin/msvc_nop.bat",
        "objcopy": "wrapper/bin/msvc_nop.bat",
        "objdump": "wrapper/bin/msvc_nop.bat",
        "strip": "wrapper/bin/msvc_nop.bat",
    },
    archiver_flags = ["/MACHINE:ARM64"],
    default_link_flags = ["/MACHINE:ARM64"],
    dbg_mode_debug_flag = "/DEBUG",
    fastbuild_mode_debug_flag = "/DEBUG",
    supports_parse_showincludes = False,
)

toolchain(
    name = "cc-toolchain-arm64_windows-clang-cl",
    exec_compatible_with = [
        "@platforms//os:windows",
        "@bazel_tools//tools/cpp:clang-cl",
    ],
    target_compatible_with = [
        "@platforms//cpu:arm64",
        "@platforms//os:windows",
    ],
    toolchain = ":cc-compiler-arm64_windows-clang-cl",
    toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
)

cc_toolchain(
    name = "cc-compiler-armeabi-v7a",
    toolchain_identifier = "stub_armeabi-v7a",
    toolchain_config = ":stub_armeabi-v7a",
    all_files = ":empty",
    ar_files = ":empty",
    as_files = ":empty",
    compiler_files = ":empty",
    dwp_files = ":empty",
    linker_files = ":empty",
    objcopy_files = ":empty",
    strip_files = ":empty",
    supports_param_files = 1,
)

armeabi_cc_toolchain_config(name = "stub_armeabi-v7a")

toolchain(
    name = "cc-toolchain-armeabi-v7a",
    exec_compatible_with = [
    ],
    target_compatible_with = [
        "@platforms//cpu:armv7",
        "@platforms//os:android",
    ],
    toolchain = ":cc-compiler-armeabi-v7a",
    toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
)
