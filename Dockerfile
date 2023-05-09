FROM quay.io/pangeo/forge:5e51a29

COPY action/deploy_recipe.py /deploy_recipe.py

ENTRYPOINT [ "sh", "/entrypoint.sh" ]
