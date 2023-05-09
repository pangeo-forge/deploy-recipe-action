import json
import os
import subprocess
import tempfile
from urllib.parse import urljoin


if __name__ == "__main__":
    # injected by github actions
    repository = os.environ["GITHUB_REPOSITORY"]  # will this fail for external prs?
    server_url = os.environ["GITHUB_SERVER_URL"]
    ref = os.environ["GITHUB_HEAD_REF"]

    # user input
    config = json.loads(os.environ["INPUT_PANGEO_FORGE_RUNNER_CONFIG"])

    # assemble https url for pangeo-forge-runner
    repo = urljoin(server_url, repository)

    print(f"{repo = }")
    print(f"{ref = }")
    print(f"{config = }")

    # TODO: dynamically install requirements.txt here
    print(f"Listing local directory")
    print(os.listdir())
    print(f"Listing feedstock sub-directory")
    print(os.listdir("feedstock"))

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
        submit_proc = subprocess.run(cmd, capture_output=True)
        stdout = submit_proc.stdout.decode()
        for line in stdout.splitlines():
            print(line)

        if submit_proc.returncode != 0:
            raise ValueError("Job submission failed.")
        else:
            lastline = json.loads(stdout.splitlines()[-1])
            job_id = lastline["job_id"]
            job_name = lastline["job_name"]
            print(f"Job submitted with {job_id = } and {job_name = }")
