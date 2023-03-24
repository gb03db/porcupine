from python:3.10-slim-bullseye

ARG WORK_UID=1001
ARG WORK_GID=1001
ENV WORK_UID=${WORK_UID}
ENV WORK_GID=${WORK_GID}

RUN groupadd --gid ${WORK_GID} usergroup && \
    useradd --comment "App user" -g ${WORK_GID} \
        --uid ${WORK_UID} --shell /sbin/nologin --home-dir /user -m user

COPY porcupine /app/porcupine
COPY requirements.pip /requirements.pip
RUN mkdir /venv && \
    chown ${WORK_UID}:${WORK_GID} /venv

USER ${WORK_UID}
RUN python -m venv /venv && \
    /venv/bin/python -m pip install -U pip && \
    /venv/bin/python -m pip install -r /requirements.pip
USER 0
RUN chown root:root /venv -R
USER ${WORK_UID}

WORKDIR /app
ENV PYTHONUNBUFFERED=yes

ENTRYPOINT ["/venv/bin/python"]
CMD ["porcupine"]

