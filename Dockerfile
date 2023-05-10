FROM quay.io/pangeo/forge:5e51a29

RUN conda run -n notebook pip install git+https://github.com/pangeo-forge/pangeo-forge-runner@main

COPY action/deploy_recipe.py /deploy_recipe.py
COPY entrypoint.sh /entrypoint.sh

ENV CONDA_ENV=notebook

ENTRYPOINT [ "sh", "/entrypoint.sh" ]
