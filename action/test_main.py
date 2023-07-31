import os
from unittest.mock import MagicMock, patch

import pytest

from deploy_recipe import main


@pytest.fixture(
    params=[
        dict(INPUT_SELECT_RECIPE_BY_LABEL=""),
        dict(INPUT_SELECT_RECIPE_BY_LABEL="true"),
    ]
)
def env(request):
    return {
        "CONDA_ENV": "notebook",
        "GITHUB_REPOSITORY": "my/repo",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_HEAD_REF": "abcdefg",
        "GITHUB_REPOSITORY_ID": "1234567890",
        "GITHUB_RUN_ID": "0987654321",
        "GITHUB_RUN_ATTEMPT": "1",
        "INPUT_PANGEO_FORGE_RUNNER_CONFIG": '{"a": "b"}',
        "INPUT_SELECT_RECIPE_BY_LABEL": request.param["INPUT_SELECT_RECIPE_BY_LABEL"],
    }


@pytest.fixture
def requests_get_returns_json():
    return [
        {"labels": [{"name": "run:my-recipe"}], "head":{"ref": "abcdefg"}}
    ]


@pytest.fixture
def subprocess_return_values():
    return dict(
        stdout='{"job_id": "foo", "job_name": "bar"}',
        stderr="",
        returncode=0,
    )


@pytest.fixture(
    params=[
        ["meta.yaml", "recipe.py"],
        ["meta.yaml", "recipe.py", "requirements.txt"]
    ]
)
def listdir_return_value(request):
    return request.param


@pytest.fixture
def mock_tempfile_name():
    return "mock-temp-file.json"


@patch("deploy_recipe.open")
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
    open: MagicMock,
    env: dict,
    requests_get_returns_json: list,
    subprocess_return_values: dict,
    listdir_return_value: list,
    mock_tempfile_name: str,
):  
    # mock a context manager, see: https://stackoverflow.com/a/28852060
    named_temporary_file.return_value.__enter__.return_value.name = mock_tempfile_name

    # mock reponse of requests.get call to github api 
    requests_get.return_value.json.return_value = requests_get_returns_json

    # mock result of subprocess call to `pangeo-forge-runner`
    subprocess_run.return_value.stdout.decode.return_value = subprocess_return_values["stdout"]
    subprocess_run.return_value.stderr.decode.return_value = subprocess_return_values["stderr"]
    subprocess_run.return_value.returncode = subprocess_return_values["returncode"]

    # mock listdir call return value
    listdir.return_value = listdir_return_value

    with patch.dict(os.environ, env):
        main()

        # open is only called if listdir('feedstock') contains requirements.txt
        # FIXME: Following fix of https://github.com/pangeo-forge/deploy-recipe-action/issues/12
        # open should never be called. Instead, subprocess.run should be called with:
        # `pip install -r requirements.txt`
        if "requirements.txt" in listdir_return_value:
            open.assert_called_once()
        else:
            open.assert_not_called()

        listdir.assert_called_once()
        
        if env["INPUT_SELECT_RECIPE_BY_LABEL"]:
            # requests.get is always called if INPUT_SELECT_RECIPE_BY_LABEL=true
            # (to check github api for PR `run:...` labels)
            requests_get.assert_called()
            
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
                        '--repo',
                        f'{env["GITHUB_SERVER_URL"]}/{env["GITHUB_REPOSITORY"]}',
                        '--ref',
                        env["GITHUB_HEAD_REF"],
                        '--json',
                        '-f',
                        mock_tempfile_name,
                        f'--Bake.recipe_id={run_labels[-1]}',
                        f'--Bake.job_name=my-recipe-1234567890-0987654321-1'
                    ],
                    capture_output=True,
                )

        else:
            # subprocess.run is always called if INPUT_SELECT_RECIPE_BY_LABEL is empty
            subprocess_run.assert_called()
