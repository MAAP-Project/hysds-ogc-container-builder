import json
import os
import copy
from pathlib import Path
from typing import List
from cwl_utils.parser import load_document_by_uri, cwl_v1_2
import urllib.parse
from utils import defaults
import re


def strip_registry(image_url: str) -> str:
    """
    Removes the registry part from a Docker image URL.
    E.g., 'docker.io/library/ubuntu' -> 'library/ubuntu'
    """
    match = re.sub(r'^([^/:]+[.][^/]+[:0-9]*)/', '', image_url)
    return match


def update_job_spec_command(job_spec_path, remote_cwl_uri):
    """
    Updates the command in the job spec to use S3 uri of the cwl yaml as 1st
    positional argument
    :return:
    """
    with open(job_spec_path) as job_spec_file:
        job_spec = json.load(job_spec_file)
        command = job_spec['command']
        command = f"{command} {remote_cwl_uri}"
        job_spec['command'] = command

    with open(job_spec_path, 'w') as f:
        json.dump(job_spec, f, indent=2)


def is_optional_type(type_):
    """
    Determines if a CWL type is optional.
    Optional types are represented as 'type?' or ['null', 'type'] in CWL.
    """
    if isinstance(type_, str):
        return type_.endswith('?')
    elif isinstance(type_, list):
        return 'null' in type_
    return False


def get_base_type(type_):
    """
    Extracts the base type from an optional type.
    'string?' -> 'string', ['null', 'string'] -> 'string'
    """
    if isinstance(type_, str):
        return type_.rstrip('?')
    elif isinstance(type_, list):
        return [t for t in type_ if t != 'null'][0] if len([t for t in type_ if t != 'null']) > 0 else None
    return type_


def parse_cwl(cwl_path):
    cwl_file = Path(cwl_path)
    cwl_obj = load_document_by_uri(cwl_file, load_all=True)
    workflow, command_line_tool = None, None
    for i in range(len(cwl_obj)):
        if type(cwl_obj[i]) == cwl_v1_2.Workflow:
            workflow = cwl_obj[i]
        elif type(cwl_obj[i]) == cwl_v1_2.CommandLineTool:
            command_line_tool = cwl_obj[i]
    return workflow, command_line_tool


def map_input_types(inp: cwl_v1_2.WorkflowInputParameter):
    input_type = inp.type_
    result = {}

    # Stringify default values for HySDS v3 compatibility
    # Only add default field if a default value exists
    if inp.default is not None:
        # Handle complex defaults (like Directory objects)
        if isinstance(inp.default, dict):
            result.update({"default": json.dumps(inp.default)})
        else:
            result.update({"default": str(inp.default)})

    # Check if type is optional
    if is_optional_type(input_type):
        result.update({"optional": True})
        input_type = get_base_type(input_type)

    # Map the base type
    if isinstance(input_type, str):
        if input_type in defaults.IO_INPUT_MAP:
            result.update({"type": defaults.IO_INPUT_MAP[input_type]})
    elif isinstance(input_type, cwl_v1_2.InputArraySchema):
        result.update({"type": "object"})
    elif isinstance(input_type, list):
        for i in input_type:
            if i in defaults.IO_INPUT_MAP:
                result.update({"type": defaults.IO_INPUT_MAP[i]})
                break

    return result


def get_id_from_uri(uri):
    fragment = urllib.parse.urlparse(uri).fragment
    return os.path.basename(fragment)


def parse_workflow_inputs(workflow_inputs: List[cwl_v1_2.WorkflowInputParameter]):
    params = []
    for inp in workflow_inputs:
        input_id = get_id_from_uri(inp.id)
        param = {
            "name": input_id,
            "from": "submitter",
        }
        # Use doc for placeholder (hint text) and label for description if available
        if inp.label:
            param["placeholder"] = inp.label
        if inp.doc:
            param["description"] = inp.doc

        param.update(map_input_types(inp))
        params.append(param)
    return params


def generate_hysds_io(workflow: cwl_v1_2.Workflow):
    # Deep copy to avoid modifying the shared default dict
    hysds_io = copy.deepcopy(defaults.HYSDS_IO)
    workflow_id = get_id_from_uri(workflow.id)
    hysds_io["label"] = workflow.label
    hysds_io["params"] = parse_workflow_inputs(workflow.inputs)
    hysds_io["description"] = workflow.doc
    return hysds_io, workflow_id


def get_input_destination(inp: cwl_v1_2.CommandInputParameter):
    """
    Determines the destination for a command-line parameter.
    - positional: if inputBinding has a position (for command-line arguments)
    - localize: if type is File or Directory (for data staging)
    - context: everything else (metadata)
    """
    # Check if this is a positional argument (has inputBinding with position)
    if hasattr(inp, 'inputBinding') and inp.inputBinding and hasattr(inp.inputBinding, 'position'):
        return {"destination": "positional"}

    # Check type for localize (File/Directory)
    input_type = inp.type_
    base_type = get_base_type(input_type) if is_optional_type(input_type) else input_type

    if isinstance(base_type, str):
        if base_type in defaults.JOB_SPEC_INPUT_MAP:
            return {"destination": defaults.JOB_SPEC_INPUT_MAP[base_type]}
    elif isinstance(base_type, cwl_v1_2.InputArraySchema):
        return {"destination": "context"}
    elif isinstance(base_type, list):
        for i in base_type:
            if i in defaults.JOB_SPEC_INPUT_MAP:
                return {"destination": defaults.JOB_SPEC_INPUT_MAP[i]}

    return {"destination": "context"}

def parse_commandline_inputs(commandline_inputs: List[cwl_v1_2.CommandInputParameter]):
    params = []
    for inp in commandline_inputs:
        input_id = get_id_from_uri(inp.id)
        param = dict({"name": input_id})
        param.update(get_input_destination(inp))
        params.append(param)
    return params


def parse_docker_requirement(docker_requirement: cwl_v1_2.DockerRequirement, docker_uri):
    req = dict()
    req["container_image_name"] = strip_registry(docker_requirement.dockerPull)
    req["container_mappings"] = dict()
    if docker_requirement.dockerImport:
        req["container_image_url"] = docker_requirement.dockerImport
    elif docker_uri and docker_uri != "":
        req["container_image_url"] = docker_uri
    return req


def parse_requirements(requirements: List[cwl_v1_2.ResourceRequirement | cwl_v1_2.DockerRequirement], docker_uri):
    """
    Parses CWL requirements and extracts resource specifications.

    Note: CWL ResourceRequirement also includes ramMin, ramMax, coresMin, coresMax
    but HySDS doesn't have direct fields for these. They could be used to determine
    recommended queues but are currently just documented here for reference.
    """
    result = dict()
    for req in requirements:
        if type(req) == cwl_v1_2.DockerRequirement:
            result["dependency_images"] = [parse_docker_requirement(req, docker_uri)]
        elif type(req) == cwl_v1_2.ResourceRequirement:
            # Extract disk usage (outdirMax in CWL is in GB)
            if hasattr(req, 'outdirMax') and req.outdirMax:
                try:
                    disk_gb = int(req.outdirMax)
                    result["disk_usage"] = f"{disk_gb}GB"
                except (ValueError, TypeError):
                    print(f"Warning: Invalid outdirMax value '{req.outdirMax}', using default 10GB")
                    result["disk_usage"] = "10GB"
            else:
                print("Warning: No outdirMax specified in ResourceRequirement, using default 10GB")
                result["disk_usage"] = "10GB"

            # Document CPU/RAM for reference (not used by HySDS directly)
            if hasattr(req, 'ramMin') and req.ramMin:
                print(f"Info: CWL specifies ramMin={req.ramMin} (not directly mapped to HySDS)")
            if hasattr(req, 'coresMin') and req.coresMin:
                print(f"Info: CWL specifies coresMin={req.coresMin} (not directly mapped to HySDS)")

    # Set default disk_usage if not found in requirements
    if "disk_usage" not in result:
        result["disk_usage"] = "10GB"

    return result


def generate_job_spec(commandline_tool: cwl_v1_2.CommandLineTool, docker_uri):
    # Deep copy to avoid modifying the shared default dict
    job_spec = copy.deepcopy(defaults.JOB_SPEC)
    job_spec["params"] = parse_commandline_inputs(commandline_tool.inputs)
    job_spec.update(parse_requirements(commandline_tool.requirements, docker_uri))

    return job_spec


def write_json(data, path):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def main(cwl_file_uri, docker_uri, algorithm_name):
    workflow, command_line_tool = parse_cwl(cwl_file_uri)
    io_spec, workflow_id = generate_hysds_io(workflow)
    job_spec = generate_job_spec(command_line_tool, docker_uri)

    out_dir = os.getcwd()
    write_json(io_spec, os.path.join(out_dir, f'hysds-io.json.{algorithm_name}'))
    write_json(job_spec, os.path.join(out_dir, f'job-spec.json.{algorithm_name}'))
    print(f"Generated hysds-io.json and job-spec.json in {out_dir}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert CWL specification to HySDS job specifications"
    )
    parser.add_argument(
        "cwl_file",
        help="Path to CWL file (must use file:// URI scheme)"
    )
    parser.add_argument(
        "algorithm_name",
        help="Process name to use in HySDS output filenames"
    )
    parser.add_argument(
        "--docker-uri",
        default="",
        help="URI of the container tarball (optional)"
    )

    args = parser.parse_args()
    main(args.cwl_file, args.docker_uri, args.algorithm_name)
