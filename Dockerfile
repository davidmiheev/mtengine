# Reproducible toolchain for mtengine. Build from the repository root:
#   docker build -f engine/Dockerfile -t mtengine .
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      macaulay2 gfan polymake singular nauty \
      python3 python3-venv git curl ca-certificates zstd \
    && rm -rf /var/lib/apt/lists/*
# Lean toolchain manager; the toolchain itself comes from formal/lean-toolchain
RUN curl -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
      | sh -s -- -y --default-toolchain none
ENV PATH=/root/.elan/bin:$PATH
WORKDIR /work
COPY formal/ formal/
RUN cd formal && lake exe cache get && lake build
COPY engine/ engine/
RUN python3 -m venv engine/.venv && engine/.venv/bin/pip install -e "engine[test]"
ENV MTENGINE_LEAN_PROJECT=/work/formal
CMD ["engine/.venv/bin/mtengine-mcp"]
