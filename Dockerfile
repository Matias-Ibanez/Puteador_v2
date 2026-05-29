FROM python:3.13-slim-bullseye

LABEL maintainer="dev"

ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
       gcc \
       libffi-dev \
       build-essential \
    && rm -rf /var/lib/apt/lists/*

ARG USER=bot
ARG UID=1000
RUN useradd --create-home --uid ${UID} ${USER}

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN chown -R ${USER}:${USER} /app

USER ${USER}

# Run as module so the `src` package is importable regardless of how the container is started
CMD ["python", "-m", "src.bot_main"]
