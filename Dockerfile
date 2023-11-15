FROM ubuntu:22.04

RUN apt-get update && apt-get install -y python3 python3-pip

# install pangeo-forge-runner. to make this faster, let's drop the pangeo-forge-recipes
# dependency from -runner (because recipes is always installed at runtime anyway)
RUN python3 -m pip install pangeo-forge-runner

COPY action/deploy_recipe.py /deploy_recipe.py
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "sh", "/entrypoint.sh" ]
