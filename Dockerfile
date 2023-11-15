FROM python:3.11-slim-bookworm

# install pangeo-forge-runner
RUN python -m pip install pangeo-forge-runner --no-deps
COPY requirements.txt /requirements.txt
RUN python -m pip install -r requirements.txt

# install numcodecs and cftime
# gcc: https://github.com/docker-library/python/issues/60#issuecomment-134322383
# numcodecs: https://github.com/zarr-developers/numcodecs/issues/421
RUN apt-get update \
    && apt-get install -y gcc \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install numcodecs cftime \
    && apt-get purge -y --auto-remove gcc

COPY action/deploy_recipe.py /deploy_recipe.py
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "sh", "/entrypoint.sh" ]
