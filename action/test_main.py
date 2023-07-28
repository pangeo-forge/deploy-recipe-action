import os
from unittest.mock import patch

from deploy_recipe import main


@patch("deploy_recipe.open")
@patch("deploy_recipe.os.listdir")
@patch("deploy_recipe.subprocess")
@patch("deploy_recipe.requests")
@patch.dict(
    os.environ,
    {
        "CONDA_ENV": "0",
        "GITHUB_REPOSITORY": "1",
        "GITHUB_SERVER_URL": "2",
        "GITHUB_API_URL": "3",
        "GITHUB_HEAD_REF": "4",
        "GITHUB_REPOSITORY_ID": "5",
        "GITHUB_RUN_ID": "6",
        "GITHUB_RUN_ATTEMPT": "7",
        "INPUT_PANGEO_FORGE_RUNNER_CONFIG": "8",
        "INPUT_SELECT_RECIPE_BY_LABEL": "9",
    },
)
def test_main(open, listdir, subprocess, requests):
    main()
