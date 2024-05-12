FROM mcr.microsoft.com/devcontainers/python:1-3.12-bullseye

RUN apt-get update \
    && export DEBIAN_FRONTEND=noninteractive \
    && dpkg --add-architecture i386 && apt-get update \
    && apt-get install -y \
        curl \
        wine32 \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && pip install -U pip && pip install --no-cache-dir poetry \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*