# syntax=docker/dockerfile:1
FROM python:3.12-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    RAJ_WORKSPACE=/workspace RAJ_UNO_PYTHON=/usr/bin/python3
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer libreoffice-calc libreoffice-impress libreoffice-draw \
    libreoffice-math libreoffice-base libreoffice-dev python3-uno \
    libreoffice-sdbc-firebird hunspell-en-us hyphen-en-us fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
ARG OPENAI=0
RUN --mount=type=secret,id=ca_bundle \
    if [ -f /run/secrets/ca_bundle ]; then export PIP_CERT=/run/secrets/ca_bundle; fi; \
    if [ "$OPENAI" = 1 ]; then pip install '.[openai]'; else pip install . 'mcp>=1.30,<2'; fi
RUN useradd --create-home --uid 10001 raj && mkdir /workspace && chown raj:raj /workspace
USER raj
ENTRYPOINT ["raj-libreoffice"]
CMD ["serve"]
