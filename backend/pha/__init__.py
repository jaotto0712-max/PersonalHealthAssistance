"""Personal Health Assistant backend.

Importing this package applies the offline runtime policy first, so the flags are in place
before any ML library (transformers, sentence-transformers, chromadb) is imported anywhere.
"""

from pha.offline import apply_offline_env

apply_offline_env()

__version__ = "0.1.0"
