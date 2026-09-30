# GigInsure: ML pipeline + API + dashboards in one image.
# The models are trained during the build, so the pickles always match the pinned scikit-learn in this image,
# and the build fails if the CI evaluation gate fails.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 PIP_NO_CACHE_DIR=1 \
    GIGINSURE_HOST=0.0.0.0 GIGINSURE_PROD=1 PORT=8000

# unprivileged user (uid 1000 is also what Hugging Face Spaces expects)
RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app . .
RUN chown app:app /app
USER app

# FAST=1 trains the 2-config grid (~1 min) instead of the full 12-config grid (~8 min)
ARG FAST=0
RUN python scripts/run_pipeline.py $([ "$FAST" = "1" ] && echo --fast) && python scripts/check_gate.py

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=4)"
CMD ["python", "scripts/serve.py", "--reset"]
