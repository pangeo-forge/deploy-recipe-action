import json
import os
import subprocess
import sys
import tempfile

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


def main():
    # set in Dockerfile
    conda_env = os.environ["CONDA_ENV"]

    # injected by github actions
    repository = os.environ["GITHUB_REPOSITORY"]  # will this fail for external prs?
    api_url = os.environ["GITHUB_API_URL"]
    head_ref = os.environ["GITHUB_HEAD_REF"]
    sha = os.environ["GITHUB_SHA"]
    repository_id = os.environ["GITHUB_REPOSITORY_ID"]
    run_id = os.environ["GITHUB_RUN_ID"]
    run_attempt = os.environ["GITHUB_RUN_ATTEMPT"]

    # user input
    config_string = os.environ["INPUT_PANGEO_FORGE_RUNNER_CONFIG"]
    select_recipe_by_label = os.environ["INPUT_SELECT_RECIPE_BY_LABEL"]

    # parse config
    print(f"pangeo-forge-runner-config provided as {config_string}")
    if os.path.exists(config_string):
        # we allow local paths pointing to json files
        print(f"Loading json from file '{config_string}'...")
        with open(config_string) as f:
            config = json.load(f)
    else:
        # or json strings passed inline in the workflow yaml
        print(f"{config_string} does not exist as a file. Loading json from string...")
        try:
            config = json.loads(config_string)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"{config_string} failed to parse to JSON. If you meant to pass a JSON string, "
                "please confirm that it is correctly formatted. If you meant to pass a filename, "
                "please confirm this path exists. Note, pangeo-forge/deploy-recipe-action should "
                "always be invoked after actions/checkout, therefore the provided path must be "
                "given relative to the repo root."
            ) from e

    # log variables to stdout
    print(f"{conda_env = }")
    print(f"{head_ref = }")
    print(f"{sha = }")
    print(f"{config = }")

    labels = []
    if select_recipe_by_label:
        # `head_ref` is available for `pull_request` events. on a `push` event, the `head_ref`
        # environment variable will be empty, so in that case we use `sha` to find the PR instead.
        commit_sha = head_ref if head_ref else sha
        # querying the following endpoint should give us the PR containing the desired labels,
        # regardless of whether this is a `pull_request` or `push` event. see official docs here:
        # https://docs.github.com/en/rest/commits/commits?apiVersion=2022-11-28#list-pull-requests-associated-with-a-commit
        pulls_url = "/".join([api_url, "repos", repository, "commits", commit_sha, "pulls"])
        headers = {"X-GitHub-Api-Version": "2022-11-28", "Accept": "application/vnd.github+json"}
        
        print(f"Fetching pulls from {pulls_url}")
        pulls_response = requests.get(pulls_url, headers=headers)
        pulls_response.raise_for_status()
        pulls = pulls_response.json()
        assert len(pulls) == 1  # pretty sure this is always true, but just making sure
        labels: list[str] = [label["name"] for label in pulls[0]["labels"]]

    recipe_ids = [l.replace("run:", "") for l in labels if l.startswith("run:")]

    # dynamically install extra deps if requested.
    # if calling `pangeo-forge-runner` directly, `--feedstock-subdir` can be passed as a CLI arg.
    # in the action context, users do not compose their own `pangeo-forge-runner` CLI calls, so if
    # they want to use a non-default value for feedstock-subdir, it must be passed via the long-form
    # name in the config JSON (i.e, `{"BaseCommand": "feedstock-subdir": ...}}`).
    feedstock_subdir = (
        config["BaseCommand"]["feedstock-subdir"]
        if "BaseCommand" in config and "feedstock-subdir" in config["BaseCommand"]
        else "feedstock"
    )
    # because we've run the actions/checkout step before reaching this point, our current
    # working directory is the root of the feedstock repo, so we can list feedstock repo
    # contents directly on the filesystem here, without requesting it from github.
    if "requirements.txt" in os.listdir(feedstock_subdir):
        to_install = f"{feedstock_subdir}/requirements.txt"
        print(f"Installing extra packages from {to_install}...")
        install_cmd = f"mamba run -n {conda_env} pip install -Ur {to_install}".split()
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
            "--repo=.",
            "--json",
            f"-f={f.name}",
        ]
        print("\nSubmitting job...")
        print(f"{recipe_ids = }")
        job_name_base = (
            f"{repository_id}-{run_id}-{run_attempt}"
        )
        if select_recipe_by_label:
            for rid in recipe_ids:
                if len(rid) > 44:
                    print(f"Recipe id {rid} is > 44 chars, truncating to 44 chars.")
                job_name = f"{rid.lower().replace('_', '-')[:44]}-{job_name_base}"
                print(f"Submitting {job_name = }")
                extra_cmd = [f"--Bake.recipe_id={rid}", f"--Bake.job_name={job_name}"]
                deploy_recipe_cmd(cmd + extra_cmd)
        else:
            extra_cmd = [f"--Bake.job_name=a{job_name_base}"]
            deploy_recipe_cmd(cmd + extra_cmd)


if __name__ == "__main__":
    sys.exit(main())
