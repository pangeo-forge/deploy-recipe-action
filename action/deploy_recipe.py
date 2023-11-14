import json
import os
import subprocess
import sys
import tempfile

import requests


def call_subprocess_run(cmd: list[str]) -> str:
    """Convenience wrapper for `subprocess.run` with stdout/stderr handling."""
    print(f"Calling subprocess with {cmd = }")
    submit_proc = subprocess.run(cmd, capture_output=True)
    stdout = submit_proc.stdout.decode()
    stderr = submit_proc.stderr.decode()
    for line in stdout.splitlines():
        print(line)

    if submit_proc.returncode != 0:
        for line in stderr.splitlines():
            print(line)
        raise ValueError(f"{cmd = } failed. See logging for details.")
    return stdout


def deploy_recipe_cmd(cmd: list[str]):
    """Wrapper for `call_subprocess_run` with extra stdout parsing when deploying recipes."""
    stdout = call_subprocess_run(cmd)
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
    config = json.loads(os.environ["INPUT_PANGEO_FORGE_RUNNER_CONFIG"])
    select_recipe_by_label = os.environ["INPUT_SELECT_RECIPE_BY_LABEL"]

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
    # name in the config JSON (i.e, `{"BaseCommand": "feedstock_subdir": ...}}`).
    feedstock_subdir = (
        config["BaseCommand"]["feedstock_subdir"]
        if "BaseCommand" in config and "feedstock_subdir" in config["BaseCommand"]
        else "feedstock"
    )
    # because we've run the actions/checkout step before reaching this point, our current
    # working directory is the root of the feedstock repo, so we can list feedstock repo
    # contents directly on the filesystem here, without requesting it from github.
    if "requirements.txt" in os.listdir(feedstock_subdir):
        call_subprocess_run(
            f"mamba run -n {conda_env} pip install -Ur {feedstock_subdir}/requirements.txt".split()
        )

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
        if select_recipe_by_label:
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


if __name__ == "__main__":
    sys.exit(main())
