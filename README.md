# HySDS OGC Container Builder

A Python utility for converting CWL (Common Workflow Language) specifications to HySDS (Hybrid Science Data System) job specifications, enabling OGC Application Packages to run on the MAAP DPS (Data Processing System).

## Overview

This tool bridges the gap between OGC-compliant workflows (defined in CWL) and the HySDS job execution framework used by NASA's MAAP platform. It generates the necessary specification files for deploying and executing containerized algorithms in the MAAP DPS environment.

## Features

- **CWL v1.2 Support**: Parses workflow and command-line tool definitions
- **Dual Spec Generation**: Creates both user-facing submission specs and internal execution specs
- **Type Mapping**: Intelligent conversion between CWL, HySDS I/O, and job parameter types
- **Docker Integration**: Normalizes container image references for HySDS
- **Resource Management**: Translates CWL resource requirements to HySDS format

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd hysds-ogc-container-builder

# Install dependencies
pip install cwl-utils
```

## Usage

```bash
python -m utils.cwl_to_hysds file://path/to/workflow.cwl <container_tarball_uri>
```

**Arguments:**
- `file://path/to/workflow.cwl`: Local path to your CWL file (must use `file://` URI scheme)
- `<container_tarball_uri>`: URI where the Docker container tarball is stored (typically S3)

**Output:**
- `hysds-io.json.<workflow_id>`: User submission interface specification
- `job-spec.json.<workflow_id>`: HySDS worker execution specification

### Example

```bash
python -m utils.cwl_to_hysds \
  file://test/process_sardem-sarsen_mlucas_nasa-ogc.cwl \
  s3://my-bucket/containers/sardem-sarsen.tar.gz
```

## Generated Specifications

### hysds-io.json
Defines the user-facing submission interface:
- Input parameters and their types
- Form field labels and placeholders
- Submission component configuration

### job-spec.json
Defines the execution environment:
- Docker container configuration
- Resource requirements (disk, time limits)
- Data localization rules
- Post-processing steps

## Architecture

The conversion process follows these steps:

1. **Parse CWL**: Extract workflow and command-line tool definitions using `cwl_utils`
2. **Map Types**: Convert CWL types to HySDS-compatible formats
3. **Generate Specs**: Create both submission and execution specifications
4. **Normalize Resources**: Transform resource requirements and container references

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation.

## Type Mappings

**CWL → hysds-io (submission interface):**
- `Directory`, `File`, `string` → `"text"`
- Array types → `"object"`

**CWL → job-spec (execution parameters):**
- `Directory`, `File` → `"localize"` (data staging)
- Other types → `"context"` (metadata)

## Project Structure

```
.
├── utils/
│   ├── cwl_to_hysds.py    # Main conversion script
│   └── defaults.py         # HySDS configuration templates
├── test/
│   └── *.cwl              # Example CWL workflows
├── CLAUDE.md              # Detailed technical documentation
└── README.md              # This file
```

## Configuration

HySDS-specific defaults are centralized in [utils/defaults.py](utils/defaults.py):

- **HYSDS_IO**: Base template for submission specs
- **JOB_SPEC**: Execution template including command wrapper, time limits, and mounted files
- **IO_INPUT_MAP**: CWL to HySDS type mappings

## Testing

Example CWL files are available in the [test/](test/) directory. The `process_sardem-sarsen_mlucas_nasa-ogc.cwl` file demonstrates a complete workflow for SAR DEM processing.

## MAAP DPS Integration

The generated specifications integrate with MAAP DPS through:
- **Wrapper Script**: `/app/dps_wrapper.sh` handles job execution
- **Environment Config**: `maap-dps.env` provides runtime configuration
- **Post-Processing**: `hysds.triage.triage` manages output handling

## Requirements

- Python 3.x
- cwl-utils library

## License

[Add license information]

## Contributing

[Add contribution guidelines]

## Support

For issues and questions, please [add contact information or issue tracker link].
