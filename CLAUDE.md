# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Python utility for converting CWL (Common Workflow Language) specifications to HySDS (Hybrid Science Data System) job specifications. The primary purpose is to bridge OGC Application Packages (defined in CWL) with the MAAP DPS (Data Processing System) job execution framework.

## Core Architecture

The conversion process in [utils/cwl_to_hysds.py](utils/cwl_to_hysds.py) follows this flow:

1. **CWL Parsing**: Uses `cwl_utils` to parse CWL v1.2 files containing both a `Workflow` and `CommandLineTool`
2. **Two-Spec Generation**: Produces two JSON files from the CWL input:
   - `hysds-io.json.<algorithm_name>`: User-facing submission interface spec (workflow-level inputs)
   - `job-spec.json.<algorithm_name>`: Execution spec for the HySDS worker (command-line tool parameters and resource requirements)

### Type Mapping Strategy

The conversion handles three distinct type systems:

- **CWL → hysds-io**: Maps CWL workflow input types to submission form types
  - `Directory`, `File`, `string` → `"text"` (see `IO_INPUT_MAP` in [utils/defaults.py](utils/defaults.py))
  - Array types → `"object"`

- **CWL → job-spec**: Maps CWL command input types to parameter destinations
  - `Directory`, `File` → `"localize"` (triggers data staging)
  - Other types → `"context"` (passed as metadata)

### Docker Image Handling

The `strip_registry()` function removes registry prefixes from Docker image URLs (e.g., `docker.io/library/ubuntu` → `library/ubuntu`) to normalize image names for HySDS's internal container management.

### Resource Requirements

Resource specifications from CWL's `ResourceRequirement` are mapped to HySDS format:
- `outdirMax` (CWL) → `disk_usage` in GB (HySDS)
- Docker requirements include both the image name and a URI to the container tarball

## Running the Converter

```bash
.venv/bin/python -m utils.cwl_to_hysds <path/to/your.cwl> <algorithm_name> [--docker-uri <URI>]
```

**Arguments**:
- `<path/to/your.cwl>`: Path to the CWL file (relative or absolute path, no `file://` prefix needed)
- `<algorithm_name>`: Algorithm/process name to use in output filenames
- `--docker-uri`: (Optional) URI where the Docker container tarball is stored (typically an S3 URI)

**Output**: Generates `hysds-io.json.<algorithm_name>` and `job-spec.json.<algorithm_name>` in the current directory.

**Example**:
```bash
.venv/bin/python -m utils.cwl_to_hysds test/process_sardem-sarsen_mlucas_nasa-ogc.cwl sardem-sarsen --docker-uri s3://bucket/container.tar.gz
```

## HySDS Integration Points

All HySDS-specific defaults are centralized in [utils/defaults.py](utils/defaults.py):

- **HYSDS_IO**: Base template for submission specs (component: "tosca", no dedup)
- **JOB_SPEC**: Execution template including:
  - Command: `/app/dps_wrapper.sh` (MAAP DPS wrapper script)
  - Time limits: 24 hours (86400s)
  - Mounted files: `maap-dps.env` configuration
  - Post-processing: `hysds.triage.triage`

## Test Data

The [test/](test/) directory contains example CWL files. The `process_sardem-sarsen_mlucas_nasa-ogc.cwl` file demonstrates a complete workflow+tool definition for SAR DEM processing with Sentinel-1 data.
