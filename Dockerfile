FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

RUN useradd --create-home --uid 10001 poc \
    && mkdir -p /opt/poc \
    && chown poc:poc /opt/poc
WORKDIR /opt/poc
COPY --chown=poc:poc workload.py /opt/poc/workload.py
COPY --chown=poc:poc allowlist_proxy.py /opt/poc/allowlist_proxy.py
USER 10001:10001
ENTRYPOINT ["python3", "/opt/poc/workload.py"]
