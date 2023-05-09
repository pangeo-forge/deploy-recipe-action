import json
import os
import subprocess
import tempfile


if __name__ == "__main__":
    repo = os.environ["INPUT_REPO"]
    ref = os.environ["INPUT_REF"]
    config = os.environ["INPUT_PANGEO_FORGE_RUNNER_CONFIG"]

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
