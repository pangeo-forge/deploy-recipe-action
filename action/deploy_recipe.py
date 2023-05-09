import json
import os
import subprocess
import tempfile


if __name__ == "__main__":
    # injected by github actions
    repository = os.environ["GITHUB_REPOSITORY"]
    server_url = os.environ["GITHUB_SERVER_URL"]
    ref = os.environ["GITHUB_SHA"]

    # user input
    config = os.environ["INPUT_PANGEO_FORGE_RUNNER_CONFIG"]

    # assemble https url for pangeo-forge-runner
    repo = server_url + repository

    print(f"{repo = }")
    print(f"{ref = }")
    print(f"{config = }")

    # TODO: dynamically install requirements.txt here

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
        assert submit_proc.returncode == 0
        lastline = json.loads(submit_proc.stdout.decode().splitlines()[-1])
        assert lastline["status"] == "submitted"
        job_id = lastline["job_id"]
        job_name = lastline["job_name"]
        print(f"Job submitted with {job_id = }")
