# Reproducible toolchain for mtengine. Build from this repository:
#   docker build -t mtengine .
#   docker run --rm mtengine .venv/bin/pytest -q          # the test suite (Lean tests skip)
#   docker run -i --rm mtengine                            # the MCP server on stdio
# The Lean backend needs a Lake project with Mathlib. Either mount one at /work/formal, e.g.
#   docker run -v /path/to/matroid_toric/formal:/work/formal mtengine
# or bake the engine's own project into the image (adds about 5 GB of prebuilt Mathlib):
#   docker build --build-arg WITH_MATHLIB=1 -t mtengine .
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      macaulay2 gfan polymake singular nauty \
      python3 python3-venv git curl ca-certificates zstd debian-keyring \
    && rm -rf /var/lib/apt/lists/*
# Regina from its official apt repository (https://regina-normal.github.io/install/ubuntu.html)
RUN curl -fsSL -o /etc/apt/sources.list.d/regina-noble.sources \
      https://regina-normal.github.io/repos/regina-noble.sources \
    && apt-get update && apt-get install -y --no-install-recommends regina-normal \
    && rm -rf /var/lib/apt/lists/*
# Lean toolchain manager; the toolchain itself comes from the mounted project's lean-toolchain
RUN curl -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
      | sh -s -- -y --default-toolchain none
ENV PATH=/root/.elan/bin:$PATH
WORKDIR /work/engine
COPY . .
RUN python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
# /work/formal, if mounted, is found as the sibling of this checkout; otherwise `mte lean-init`'s
# project in ~/.local/share/mtengine/lean is used.
ARG WITH_MATHLIB=0
RUN if [ "$WITH_MATHLIB" = 1 ]; then .venv/bin/mte lean-init; fi
CMD [".venv/bin/mtengine-mcp"]
