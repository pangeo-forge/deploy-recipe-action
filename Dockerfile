FROM ubuntu:22.04

# git is to support pip install from `git+https://` sources
RUN apt-get update && apt-get install -y python3 python3-pip git
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install "pangeo-forge-runner>=0.9.2"

COPY action/deploy_recipe.py /deploy_recipe.py
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "sh", "/entrypoint.sh" ]
