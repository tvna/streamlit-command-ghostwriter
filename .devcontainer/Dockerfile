FROM mcr.microsoft.com/devcontainers/python:3.13-bullseye@sha256:c30134ea443e4f450595a814ca2c09ae753bfee1e777581c2ab6f2961c002a70

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