---
title: MLflow server for Getaround Analysis
emoji: 📊
colorFrom: purple
colorTo: indigo
sdk: docker
pinned: false
---

### Fonctionnement
```
push from main (files in spaces/mlflow/)
        ↓
GitHub Action is triggered
        ↓
git init + commit of the contents from spaces/mlflow/
        ↓
force-push to huggingface.co/spaces/...
        ↓
HF Space automatically rebuilds the Docker
```
