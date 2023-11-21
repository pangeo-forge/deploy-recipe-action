FROM ubuntu:22.04

RUN apt-get update && apt-get install -y python3 python3-pip
RUN python3 -m pip install pangeo-forge-runner

COPY action/deploy_recipe.py /deploy_recipe.py
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "sh", "/entrypoint.sh" ]
