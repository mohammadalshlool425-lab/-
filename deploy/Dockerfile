# عزوتك production image: non-root runtime, no development assets or secrets.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    BIND_HOST=0.0.0.0

RUN groupadd --system --gid 10001 ezwatek \
    && useradd --system --uid 10001 --gid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin ezwatek

WORKDIR /app
COPY requirements-production.txt ./
RUN python -m pip install --no-cache-dir --requirement requirements-production.txt

COPY app.py config.py jobs.py oidc.py repository.py security.py worker.py ./
COPY favicon.svg manifest.webmanifest robots.txt ./
COPY scripts ./scripts
COPY db ./db

RUN chown -R ezwatek:ezwatek /app
USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=3).read()"

ENTRYPOINT ["python", "app.py"]
