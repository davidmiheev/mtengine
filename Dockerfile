# Reproducible toolchain for mtengine. Build from this repository:
#   docker build -t mtengine .
# The Lean backend needs a Lake project with Mathlib; mount one at /work/formal, e.g.
#   docker run -v /path/to/matroid_toric/formal:/work/formal mtengine
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      macaulay2 gfan polymake singular nauty \
      python3 python3-venv git curl ca-certificates zstd \
    && rm -rf /var/lib/apt/lists/*
# Lean toolchain manager; the toolchain itself comes from the mounted project's lean-toolchain
RUN curl -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
      | sh -s -- -y --default-toolchain none
ENV PATH=/root/.elan/bin:$PATH
WORKDIR /work/engine
COPY . .
RUN python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
ENV MTENGINE_LEAN_PROJECT=/work/formal
CMD [".venv/bin/mtengine-mcp"]
