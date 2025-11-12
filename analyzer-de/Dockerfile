FROM mcr.microsoft.com/presidio-analyzer:latest

# 1) Install spaCy + German model
RUN pip install --no-cache-dir "spacy==3.7.2" && \
    pip install --no-cache-dir \
      https://github.com/explosion/spacy-models/releases/download/de_core_news_md-3.7.0/de_core_news_md-3.7.0-py3-none-any.whl

# Note: Keep base image working directory (where pyproject.toml lives)
# All our files go to /app but we don't change WORKDIR

# 2) Copy OpenPLZ data (CSV and preprocessed pickle for fast loading)
COPY data/streets.csv /app/data/streets.csv
COPY data/streets_normalized.pkl /app/data/streets_normalized.pkl

# 3) Copy gazetteer component + sitecustomize to where Python can find them
# Base image should have /app or similar on PYTHONPATH already
COPY street_gazetteer.py /app/street_gazetteer.py
COPY sitecustomize.py    /app/sitecustomize.py

# Add /app to PYTHONPATH to ensure modules are found
ENV PYTHONPATH=/app:$PYTHONPATH

# 4) Copy build script and build custom model
COPY build_de_address_model.py /app/build_de_address_model.py
RUN python /app/build_de_address_model.py

# 5) Configs
COPY analyzer-conf.yml     /app/conf/analyzer-conf.yml
COPY nlp-config-de.yml     /app/conf/nlp-config-de.yml
COPY recognizers-de.yml    /app/conf/recognizers-de.yml

EXPOSE 3000
