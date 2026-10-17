import os, tempfile
# isolate the result cache from the user's cache during tests
os.environ.setdefault("MTENGINE_CACHE", tempfile.mkdtemp(prefix="mte-test-cache-"))
