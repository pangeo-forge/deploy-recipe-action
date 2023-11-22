FROM ubuntu:22.04
# label image to make it public, see:
# https://dev.to/willvelida/pushing-container-images-to-github-container-registry-with-github-actions-1m6b
LABEL org.opencontainers.image.source="https://github.com/pangeo-forge/deploy-recipe-action"

# git is to support pip install from `git+https://` sources
RUN apt-get update && apt-get install -y python3 python3-pip git
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install "pangeo-forge-runner[dataflow,flink]>=0.9.2"

COPY action/deploy_recipe.py /deploy_recipe.py
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "sh", "/entrypoint.sh" ]
