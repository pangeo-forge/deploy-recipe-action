import os
from unittest.mock import MagicMock, patch

from deploy_recipe import main


@patch("deploy_recipe.open")
@patch("deploy_recipe.os.listdir")
@patch("deploy_recipe.subprocess.run")
@patch("deploy_recipe.requests")
@patch.dict(
    os.environ,
    {
        "CONDA_ENV": "notebook",
        "GITHUB_REPOSITORY": "my/repo",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_HEAD_REF": "abcdefg",
        "GITHUB_REPOSITORY_ID": "1234567890",
        "GITHUB_RUN_ID": "0987654321",
        "GITHUB_RUN_ATTEMPT": "1",
        "INPUT_PANGEO_FORGE_RUNNER_CONFIG": '{"a": "b"}',
        "INPUT_SELECT_RECIPE_BY_LABEL": "",
    },
)
def test_main(
    requests: MagicMock,
    subprocess_run: MagicMock,
    listdir: MagicMock,
    open: MagicMock,
):
    class MockProcess:
        stdout = b'{"job_id": "foo", "job_name": "bar"}'
        stderr = b"456"
        returncode = 0

    subprocess_run.return_value = MockProcess()
    main()
    # open is only called if listdir('feedstock') contains requirements.txt
    # open.assert_called_once()
    listdir.assert_called_once()
    subprocess_run.assert_called()
    # requests is only called if INPUT_SELECT_RECIPE_BY_LABEL=true
    # requests.assert_called()
