import json
import os
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

    json.dump(job_spec, open(job_spec_path, 'r'), indent=2)


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
    result.update({"default": inp.default if inp.default else ""})
    if isinstance(input_type, str):
        if input_type in defaults.IO_INPUT_MAP:
            result.update({"type": defaults.IO_INPUT_MAP[input_type]})
    elif isinstance(input_type, cwl_v1_2.InputArraySchema):
        result.update({"type": "object"})
    elif isinstance(input_type, list):
        for i in input_type:
            if i in defaults.IO_INPUT_MAP:
                result.update({"type": defaults.IO_INPUT_MAP[i]})
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
            "description": inp.doc,
            "from": "submitter",
            "placeholder": inp.label
        }
        param.update(map_input_types(inp))
        params.append(param)
    return params


def generate_hysds_io(workflow: cwl_v1_2.Workflow):
    hysds_io = defaults.HYSDS_IO
    workflow_id = get_id_from_uri(workflow.id)
    hysds_io["label"] = workflow.label
    hysds_io["params"] = parse_workflow_inputs(workflow.inputs)
    hysds_io["description"] = workflow.doc
    return hysds_io, workflow_id


def get_input_destination(inp: cwl_v1_2.CommandInputParameter):
    input_type = inp.type_
    if isinstance(input_type, str):
        if input_type in defaults.JOB_SPEC_INPUT_MAP:
            return {"destination": defaults.JOB_SPEC_INPUT_MAP[input_type]}
    elif isinstance(input_type, cwl_v1_2.InputArraySchema):
        return {"destination": "context"}
    elif isinstance(input_type, list):
        for i in input_type:
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
    else:
        req["container_image_url"] = docker_uri
    return req


def parse_requirements(requirements: List[cwl_v1_2.ResourceRequirement | cwl_v1_2.DockerRequirement], docker_uri):
    result = dict()
    for req in requirements:
        if type(req) == cwl_v1_2.DockerRequirement:
            result["dependency_images"] = [parse_docker_requirement(req, docker_uri)]
        elif type(req) == cwl_v1_2.ResourceRequirement:
            result["disk_usage"] = f"{req.outdirMax}GB"
    return result


def generate_job_spec(commandline_tool: cwl_v1_2.CommandLineTool, docker_uri):
    job_spec = defaults.JOB_SPEC
    job_spec["params"] = parse_commandline_inputs(commandline_tool.inputs)
    job_spec.update(parse_requirements(commandline_tool.requirements, docker_uri))

    return job_spec


def write_json(data, path):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def main(cwl_file_uri, docker_uri):
    workflow, command_line_tool = parse_cwl(cwl_file_uri)
    io_spec, workflow_id = generate_hysds_io(workflow)
    job_spec = generate_job_spec(command_line_tool, docker_uri)

    out_dir = os.getcwd()
    write_json(io_spec, os.path.join(out_dir, f'hysds-io.json.{workflow_id}'))
    write_json(job_spec, os.path.join(out_dir, f'job-spec.json.{workflow_id}'))
    print(f"Generated hysds-io.json and job-spec.json in {out_dir}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python cwl_to_hysds.py file://path/to/your.cwl <URI of the container tarball>")
    else:
        main(sys.argv[1], sys.argv[2])
