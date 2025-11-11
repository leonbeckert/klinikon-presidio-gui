FROM mcr.microsoft.com/presidio-analyzer:latest

# spaCy und deutsches Modell installieren
RUN pip install --no-cache-dir spacy==3.7.2 && \
    pip install --no-cache-dir https://github.com/explosion/spacy-models/releases/download/de_core_news_md-3.7.0/de_core_news_md-3.7.0-py3-none-any.whl

# Copy build script and create custom model with ADDRESS EntityRuler
COPY build_de_address_model.py /app/build_de_address_model.py
RUN python /app/build_de_address_model.py

# Drei separate Config-Dateien (Analyzer + NLP + Recognizer Registry)
COPY analyzer-conf.yml /app/conf/analyzer-conf.yml
COPY nlp-config-de.yml /app/conf/nlp-config-de.yml
COPY recognizers-de.yml /app/conf/recognizers-de.yml

EXPOSE 3000
