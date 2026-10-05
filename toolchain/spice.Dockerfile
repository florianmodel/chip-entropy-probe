FROM debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251
RUN apt-get update && apt-get install -y --no-install-recommends ngspice=39.3+ds-1 python3=3.11.2-1+b1 && rm -rf /var/lib/apt/lists/*
WORKDIR /work
