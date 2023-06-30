import json
import os
import subprocess
import tempfile
from urllib.parse import urljoin

import requests


def deploy_recipe_cmd(cmd: list[str]):
    print(f"Calling subprocess with {cmd = }")
    submit_proc = subprocess.run(cmd, capture_output=True)
    stdout = submit_proc.stdout.decode()
    stderr = submit_proc.stderr.decode()
    for line in stdout.splitlines():
        print(line)

    if submit_proc.returncode != 0:
        for line in stderr.splitlines():
            print(line)
        raise ValueError("Job submission failed.")
    else:
        lastline = json.loads(stdout.splitlines()[-1])
        job_id = lastline["job_id"]
        job_name = lastline["job_name"]
        print(f"Job submitted with {job_id = } and {job_name = }")


if __name__ == "__main__":
    # set in Dockerfile
    conda_env = os.environ["CONDA_ENV"]

    # injected by github actions
    repository = os.environ["GITHUB_REPOSITORY"]  # will this fail for external prs?
    server_url = os.environ["GITHUB_SERVER_URL"]
    api_url = os.environ["GITHUB_API_URL"]
    ref = os.environ["GITHUB_HEAD_REF"]
    repository_id = os.environ["GITHUB_REPOSITORY_ID"]
    run_id = os.environ["GITHUB_RUN_ID"]
    run_attempt = os.environ["GITHUB_RUN_ATTEMPT"]

    # user input
    config = json.loads(os.environ["INPUT_PANGEO_FORGE_RUNNER_CONFIG"])
    select_recipe_by_label = os.environ["INPUT_SELECT_RECIPE_BY_LABEL"]

    # assemble https url for pangeo-forge-runner
    repo = urljoin(server_url, repository)

    # log variables to stdout
    print(f"{conda_env = }")
    print(f"{repo = }")
    print(f"{ref = }")
    print(f"{config = }")

    labels = []
    if select_recipe_by_label:
        # iterate through PRs on the repo. if the PR's head ref is the same
        # as our ``ref`` here, get the labels from that PR, and stop iteration.
        # FIXME: what if this is a push event, and not a pull_request event?
        pulls_url = "/".join([api_url, "repos", repository, "pulls"])
        print(f"Fetching pulls from {pulls_url}")
        
        pulls_response = requests.get(pulls_url)
        pulls_response.raise_for_status()
        pulls = pulls_response.json()

        for p in pulls:
            if p["head"]["ref"] == ref:
                labels: list[str] = [label["name"] for label in p["labels"]]
    recipe_ids = [l.replace("run:", "") for l in labels if l.startswith("run:")]

    # dynamically install extra deps if requested.
    # because we've run the actions/checkout step before reaching this point, our current
    # working directory is the root of the feedstock repo, so we can list feedstock repo
    # contents directly on the filesystem here, without requesting it from github.
    if "requirements.txt" in os.listdir("feedstock"):
        with open("feedstock/requirements.txt") as f:
            to_install = f.read().splitlines()

        print(f"Installing extra packages {to_install}...")
        install_cmd = f"mamba run -n {conda_env} pip install -U".split() + to_install
        install_proc = subprocess.run(install_cmd, capture_output=True, text=True)
        if install_proc.returncode != 0:
            # installations failed, so record the error and bail early
            ValueError(f"Installs failed with {install_proc.stderr = }")

    with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
        json.dump(config, f)
        f.flush()
        cmd = [
            "pangeo-forge-runner",
            "bake",
            "--repo",
            repo,
            "--ref",
            ref,
            "--json",
            "-f",
            f.name,
        ]
        print("\nSubmitting job...")
        print(f"{recipe_ids = }")
        if recipe_ids:
            for rid in recipe_ids:
                if len(rid) > 44:
                    print(f"Recipe id {rid} is > 44 chars, truncating to 44 chars.")
                job_name = (
                    f"{rid.lower().replace('_', '-')[:44]}-{repository_id}-{run_id}-{run_attempt}"
                )
                print(f"Submitting {job_name = }")
                extra_cmd = [f"--Bake.recipe_id={rid}", f"--Bake.job_name={job_name}"]
                deploy_recipe_cmd(cmd + extra_cmd)
        else:
            # FIXME: pangeo-forge-runner handles job_name generation if we deploy everything
            # currently, there is a pangeo-forge-runne bug that prevents creation of unique
            # job_names when everything is deployed. apart from fixing that bug, we'd like the
            # ability to provide our own job names, even if we deploy everything. this might mean
            # passing a `--Bake.job_name_append` option to pangeo-forge-runner, which is a user-
            # defined string to append to the job names.
            deploy_recipe_cmd(cmd)
