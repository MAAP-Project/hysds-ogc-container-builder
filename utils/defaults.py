HYSDS_IO = {
    "component": "tosca",
    "submission_type": "individual",
    "enable_dedup": False,
    "action-type": "both"
}

IO_INPUT_MAP = {
    "Directory": "text",
    "File": "text",
    "string": "text",
    "int": "number",
    "long": "number",
    "float": "number",
    "double": "number",
    "boolean": "boolean",
}

JOB_SPEC_INPUT_MAP = {
    "Directory": "localize",
    "File": "localize"
}

JOB_SPEC = {
    "imported_worker_files": {
    "${HYSDS_ROOT_WORK_DIR}/etc/maap-dps.env": "/maap-dps.env",
    "/tmp": [
      "/tmp",
      "rw"
    ]
  },
    "soft_time_limit": 86400,
    "time_limit": 86400,
    "command": "/app/dps_wrapper.sh",
    "post": ["hysds.triage.triage"]
}


# Output target params (MAAP-Project/Community#1336). Always added to every
# algorithm so the API can route job outputs to an org bucket/prefix.
# - hysds-io: optional, no default -> Mozart skips them when not submitted and
#   the executor falls back to $DEFAULT_OUTPUT_BUCKET + username.
# - job-spec: destination "context" -> Mozart merges them into the payload
#   (_context.json), where maap-cwltool-executor reads them. They are not CWL
#   inputs and are never passed to cwltool.
OUTPUT_TARGET_IO_PARAMS = [
    {
        "name": "output_bucket",
        "from": "submitter",
        "type": "text",
        "optional": True,
        "description": "S3 bucket for job outputs (set by the MAAP API)",
    },
    {
        "name": "output_prefix",
        "from": "submitter",
        "type": "text",
        "optional": True,
        "description": "Key prefix in output_bucket for job outputs (set by the MAAP API)",
    },
]

OUTPUT_TARGET_JOB_SPEC_PARAMS = [
    {"name": "output_bucket", "destination": "context"},
    {"name": "output_prefix", "destination": "context"},
]
