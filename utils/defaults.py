HYSDS_IO = {
    "component": "tosca",
    "submission_type": "individual",
    "enable_dedup": False,
    "action-type": "both"
}

IO_INPUT_MAP = {
    "Directory": "text",
    "File": "text",
    "string": "text"
}

JOB_SPEC_INPUT_MAP = {
    "Directory": "localize",
    "File": "localize"
}

JOB_SPEC = {
    "imported_worker_files": {
        "$HOME/verdi/etc/maap-dps.env": "/maap-dps.env",
        "/tmp": ["/tmp", "rw"]
    },
    "soft_time_limit": 86400,
    "time_limit": 86400,
    "command": "/app/dps_wrapper.sh",
    "post": ["hysds.triage.triage"]
}