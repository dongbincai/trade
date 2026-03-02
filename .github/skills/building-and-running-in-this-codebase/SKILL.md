---
name: building-and-running-in-this-codebase
description: Use when building, testing, or running targets in this Bazel/make8 monorepo. CRITICAL - certain large targets (visualization_main, olive_main, headless_simulation_main) REQUIRE make8, not bazel. Also covers required flags and Python runtime configs.
---

# Building and Running in This Codebase

## Overview

This repo uses Bazel for most builds/tests, and `make8` for some large targets and Python runtime setups.

## Hard Rules

- **Bazel**: Always add `-c opt --config remote --jobs 8`.
- **Targets under `map/training/pytorch`**: When building/testing/running via **either** `bazel` or `make8`, also add `--config=system_py310`.
  - Multiple `--config` flags are allowed (e.g. `--config remote --config system_py310`).

## Quick Reference

### Bazel

- Build: `bazel build -c opt --config remote --jobs 8 //path/to:target`
- Test: `bazel test -c opt --config remote --jobs 8 //path/to:target`
- Run: `bazel run -c opt --config remote --jobs 8 //path/to:target -- --flag=value`

#### Bazel for `map/training/pytorch` targets

- Build: `bazel build -c opt --config remote --config system_py310 --jobs 8 //map/training/pytorch/...:target`
- Test: `bazel test -c opt --config remote --config system_py310 --jobs 8 //map/training/pytorch/...:target`
- Run: `bazel run -c opt --config remote --config system_py310 --jobs 8 //map/training/pytorch/...:target -- --flag=value`

### make8

- **Large targets (REQUIRED, do NOT use bazel)**: `make8 build <target>`
  - `visualization_main`
  - `olive_main`
  - `headless_simulation_main`
  - `run_data_generation`

### map/training/pytorch Python programs

- Build + run (example):

```bash
make8 build --config=system_py310 //map/training/pytorch/abnormal_measurement_detection/dataset:run_data_generation \
  && ./make8-bin/map/training/pytorch/abnormal_measurement_detection/dataset/run_data_generation \
    --simple_mode navis \
    --remote_dir /path/to/data.atomic.zip \
    --result_dir /tmp/local_data_export/train \
    --export_mode abnormal_measurement_detection \
    --remove_cached_records=False \
    --extra_flags="--static_map_any_version --road_graph_any_version"
```

- Run via Bazel (example):

```bash
bazel run -c opt --config remote --config system_py310 --jobs 8 \
  //map/training/pytorch/abnormal_measurement_detection/visualization:visualize_hdf5
```

## Common Mistakes

- Running Bazel without `-c opt --config remote --jobs 8` and getting inconsistent behavior/perf.
- Building `map/training/pytorch` Python targets without `--config=system_py310` and hitting interpreter/deps mismatch.
