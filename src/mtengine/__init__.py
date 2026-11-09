"""mtengine: one interface to the tools used in the matroid_toric project.

Layers:
  core      -- process runner, content-addressed result cache with provenance, job queue
  backends  -- thin adapters: macaulay2, gfan, polymake, singular, nauty, lean, regina
  domain    -- mathematics built on the backends (Hessenberg varieties, GKM graphs, posets)
  api       -- the public functions; the CLI (`mte`) and the MCP server expose exactly these
"""
__version__ = "0.1.0"
