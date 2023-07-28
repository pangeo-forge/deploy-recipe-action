import os
from dataclasses import dataclass
from typing import TypedDict
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


class MockPRLabels(TypedDict):
    name: str


class MockPRHead(TypedDict):
    ref: str


class MockGitHubPullsResponse(TypedDict):
    labels: list[MockPRLabels]
    head: MockPRHead


@dataclass
class MockRequestsGetResponse:
    _json: list[MockGitHubPullsResponse]

    def json(self) -> list[MockGitHubPullsResponse]:
        return self._json

    def raise_for_status(self):
        pass


@pytest.fixture
def requests_get_return_value():
    return MockRequestsGetResponse(
        _json=[
            {"labels": [{"name": "run:my-recipe"}], "head":{"ref": "abcdefg"}}
        ],
    )


@dataclass
class MockProcess:
    stdout: bytes
    stderr: bytes
    returncode: int


@pytest.fixture
def subprocess_return_value():
    return MockProcess(
        stdout=b'{"job_id": "foo", "job_name": "bar"}',
        stderr=b"",
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


class MockNamedTemporaryFile:
    name = "mock-temp-file"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def write(self, *args):
        pass

    def flush(self):
        pass


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
    requests_get_return_value: MockRequestsGetResponse,
    subprocess_return_value: MockProcess,
    listdir_return_value: list,
):  
    mock_named_temporary_file = MockNamedTemporaryFile()
    named_temporary_file.return_value = mock_named_temporary_file

    requests_get.return_value = requests_get_return_value
    subprocess_run.return_value = subprocess_return_value
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
                for pull_request in requests_get_return_value.json()
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
                        mock_named_temporary_file.name,
                        f'--Bake.recipe_id={run_labels[-1]}',
                        f'--Bake.job_name=my-recipe-1234567890-0987654321-1'
                    ],
                    capture_output=True,
                )

        else:
            # subprocess.run is always called if INPUT_SELECT_RECIPE_BY_LABEL is empty
            subprocess_run.assert_called()
