import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# actions do not require an installed package (action module is run as script)
# to get tests separated into a different directory (among other things, allows
# clearer differentiation of coverage), add `action` dir to PATH.
sys.path.append((Path(__file__).parent.parent / "action").absolute().as_posix())
from deploy_recipe import main  # type: ignore


@pytest.fixture(params=["", "abcdefg"], ids=["no_head_ref", "has_head_ref"])
def head_ref(request):
    return request.param


@pytest.fixture(params=["", "true"], ids=["no_label", "select_by_label"])
def select_recipe_by_label(request):
    return request.param


@pytest.fixture(params=["inline", "file", "broken_inline", "broken_file"])
def pangeo_forge_runner_config(request, tmp_path_factory: pytest.TempPathFactory):
    if "inline" in request.param:
        return "{}" if not "broken" in request.param else "{broken: json}"
    elif "file" in request.param:
        if not "broken" in request.param:
            tmp_config_dir = tmp_path_factory.mktemp("config")
            outpath = tmp_config_dir / "config.json"
            with open(tmp_config_dir / "config.json", mode="w") as f:
                json.dump({}, f)
            return outpath.absolute().as_posix()
        else:
            return "non/existent/path.json"


@pytest.fixture
def env(select_recipe_by_label, head_ref, pangeo_forge_runner_config):
    return {
        "GITHUB_REPOSITORY": "my/repo",
        "GITHUB_API_URL": "https://api.github.com",
        # fixturing of `head_ref` reflects that on `push`
        # events, `GITHUB_HEAD_REF` env var is empty
        "GITHUB_HEAD_REF": head_ref,
        "GITHUB_SHA": "gfedcba",
        "GITHUB_REPOSITORY_ID": "1234567890",
        "GITHUB_RUN_ID": "0987654321",
        "GITHUB_RUN_ATTEMPT": "1",
        "INPUT_PANGEO_FORGE_RUNNER_CONFIG": pangeo_forge_runner_config,
        "INPUT_SELECT_RECIPE_BY_LABEL": select_recipe_by_label,
    }


@pytest.fixture
def requests_get_returns_json():
    return [
        {"labels": [{"name": "run:my-recipe"}]}
    ]


@dataclass
class MockCompletedProcess:
    stdout: bytes
    stderr: bytes
    returncode: int


@pytest.fixture(params=[True, False], ids=["has_job_id", "no_job_id"])
def subprocess_run_side_effect(request):
    def _get_mock_completed_proc(cmd: list[str], *args, **kwargs):
        # `subprocess.run` is called a few ways, so use a side effect function
        # to vary the output depending on what arguments it was called with.
        if "pip install" in " ".join(cmd):
            returncode = 0 if not "broken-requirements-feedstock" in " ".join(cmd) else 1
            return MockCompletedProcess(
                stdout=b"",
                stderr=b"",
                returncode=returncode,
            )
        elif "bake" in " ".join(cmd):
            # not all bakery types have a job_id, represent that here
            has_job_id = request.param
            stdout = b'{"job_id": "foo", "job_name": "bar"}' if has_job_id else b'{}'
            return MockCompletedProcess(
                stdout=stdout,
                stderr=b"",
                returncode=0,
            )
        else:
            raise NotImplementedError(
                f"We only expect `pip install` and `bake` commands, got {cmd = }."
            )
    return _get_mock_completed_proc


@pytest.fixture(
    params=[
        (["meta.yaml", "recipe.py"], False),
        (["meta.yaml", "recipe.py", "requirements.txt"], False),
        # represents case where `pip install -r requirements.txt` raises error
        (["meta.yaml", "recipe.py", "requirements.txt"], True),
    ],
    ids=["no_reqs", "has_reqs", "broken_reqs"],
)
def listdir_return_value_with_pip_install_raises(request):
    return request.param


@pytest.fixture
def mock_tempfile_name():
    return "mock-temp-file.json"


def get_config_asdict(config: str) -> dict:
    """Config could be a JSON file path or JSON string, either way load it to dict."""
    if os.path.exists(config):
        with open(config) as f:
            return json.load(f)
    return json.loads(config)


@patch("deploy_recipe.os.listdir")
@patch("deploy_recipe.subprocess.run")
@patch("deploy_recipe.requests.get")
@patch("deploy_recipe.tempfile.NamedTemporaryFile")
def test_main(
    # Note that patches are passed to `test_main` by order, not name. 
    # See https://docs.python.org/3/library/unittest.mock.html#quick-guide:
    # "When you nest patch decorators the mocks are passed in to the decorated
    # function in the same order they applied (the normal Python order that
    # decorators are applied). This means from the bottom up..."
    named_temporary_file: MagicMock,
    requests_get: MagicMock,
    subprocess_run: MagicMock,
    listdir: MagicMock,
    env: dict,
    requests_get_returns_json: list,
    subprocess_run_side_effect: dict,
    listdir_return_value_with_pip_install_raises: tuple[str],
    mock_tempfile_name: str,
):  
    # mock a context manager, see: https://stackoverflow.com/a/28852060
    named_temporary_file.return_value.__enter__.return_value.name = mock_tempfile_name

    # mock reponse of requests.get call to github api 
    requests_get.return_value.json.return_value = requests_get_returns_json

    # mock result of subprocess calls
    subprocess_run.side_effect = subprocess_run_side_effect

    # mock listdir call return value, and pip install side effect
    listdir_return_value, pip_install_raises = listdir_return_value_with_pip_install_raises
    listdir.return_value = listdir_return_value

    config_is_broken = (
        env["INPUT_PANGEO_FORGE_RUNNER_CONFIG"] == "{broken: json}"
        or env["INPUT_PANGEO_FORGE_RUNNER_CONFIG"] == "non/existent/path.json"
    )

    if pip_install_raises and not config_is_broken:
        update_with = {"BaseCommand": {"feedstock_subdir": "broken-requirements-feedstock"}}
        config = get_config_asdict(env["INPUT_PANGEO_FORGE_RUNNER_CONFIG"])
        config.update(update_with)

        if os.path.exists(env["INPUT_PANGEO_FORGE_RUNNER_CONFIG"]):
            with open(env["INPUT_PANGEO_FORGE_RUNNER_CONFIG"], "w") as f:
                json.dump(config, f)
        else:
            env["INPUT_PANGEO_FORGE_RUNNER_CONFIG"] = json.dumps(config)

    with patch.dict(os.environ, env):
        if (
            not config_is_broken
            and "broken-requirements-feedstock" in str(
                get_config_asdict(env["INPUT_PANGEO_FORGE_RUNNER_CONFIG"])
            )
        ):
            with pytest.raises(ValueError):
                main()
            # if pip install fails, we should bail early & never invoke `bake`. re: `call_args_list`:
            # https://docs.python.org/3/library/unittest.mock.html#unittest.mock.Mock.call_args_list
            for call in [args[0][0] for args in subprocess_run.call_args_list]:
                assert "bake" not in call
        elif env["INPUT_PANGEO_FORGE_RUNNER_CONFIG"] == "{broken: json}":
            with pytest.raises(ValueError):
                main()
        elif env["INPUT_PANGEO_FORGE_RUNNER_CONFIG"] == "non/existent/path.json":
            with pytest.raises(ValueError):
                main()
        else:
            main()

            if any([path.endswith("requirements.txt") for path in listdir_return_value]):
                config = get_config_asdict(env["INPUT_PANGEO_FORGE_RUNNER_CONFIG"])
                feedstock_subdir = (
                    config["BaseCommand"]["feedstock-subdir"]
                    if "BaseCommand" in config
                    else "feedstock"
                )
                expected_cmd = (
                    f"python3 -m pip install -Ur {feedstock_subdir}/requirements.txt"
                ).split()
                subprocess_run.assert_any_call(expected_cmd, capture_output=True)
            else:
                # if 'requirements.txt' not present, 'pip' is never invoked.
                # re: `call_args_list`: see link in comment in `if pip_install_raises:` block above.
                for call in [args[0][0] for args in subprocess_run.call_args_list]:
                    assert "pip" not in call

            listdir.assert_called_once()

            if env["INPUT_SELECT_RECIPE_BY_LABEL"]:
                # requests.get is always called if INPUT_SELECT_RECIPE_BY_LABEL=true (to check github
                # api for PR `run:...` labels). if this is a `pull_request` event, the called gh api
                # url should contain the `GITHUB_HEAD_REF` for that PR. if this is a `push` event
                # (reflected in the env by the fact that `GITHUB_HEAD_REF` is empty), then we expect to
                # be calling an api url for the `GITHUB_SHA` associated with the `push`.
                called_gh_api_url = requests_get.call_args[0][0]
                if env["GITHUB_HEAD_REF"]:
                    assert env["GITHUB_HEAD_REF"] in called_gh_api_url
                else:
                    assert env["GITHUB_SHA"] in called_gh_api_url

                run_labels = [
                    label["name"].split("run:")[-1]
                    for pull_request in requests_get_returns_json
                    for label in pull_request["labels"]
                    if label["name"].startswith("run:")
                ]
                if run_labels:
                    subprocess_run.assert_called_with(
                        [
                            'pangeo-forge-runner',
                            'bake',
                            '--repo=.',
                            '--json',
                            f'-f={mock_tempfile_name}',
                            f'--Bake.recipe_id={run_labels[-1]}',
                            f'--Bake.job_name=my-recipe-1234567890-0987654321-1'
                        ],
                        capture_output=True,
                    )

            else:
                # subprocess.run is always called if INPUT_SELECT_RECIPE_BY_LABEL is empty
                subprocess_run.assert_called()
