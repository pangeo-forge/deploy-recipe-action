FROM python:3.11-slim-bookworm

# install numcodecs and cftime, which require gcc because wheels are not available
# manually install gcc here (rather than using a base image that includes it), so
# we have a clean way to remove it if/when wheels are available.
# gcc: https://github.com/docker-library/python/issues/60#issuecomment-134322383
# numcodecs: https://github.com/zarr-developers/numcodecs/issues/421
RUN apt-get update \
    && apt-get install -y gcc \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install numcodecs cftime \
    && apt-get purge -y --auto-remove gcc
# alternatively, if numcodecs and/or cftime are not needed at compile time, perhaps
# a lighter "compile-only" dependency set can be created for pangeo-forge-recipes?

# install pangeo-forge-runner. to make this faster, let's drop the pangeo-forge-recipes
# dependency from -runner (because recipes is always installed at runtime anyway)
RUN python -m pip install pangeo-forge-runner

COPY action/deploy_recipe.py /deploy_recipe.py
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "sh", "/entrypoint.sh" ]
