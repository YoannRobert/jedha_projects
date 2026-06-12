# Dockerfile pour Hugging Face Space
# Python 3.10 pour s'aligner sur l'environnement d'entraînement du modèle
FROM python:3.10-slim

# HF Space recommande un user non-root avec UID 1000
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Installation des dépendances en premier pour bénéficier du cache Docker
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copie du code applicatif
COPY --chown=user . .

# HF Space attend par défaut le port 7860
EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
