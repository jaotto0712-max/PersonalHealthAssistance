"""Personal Health Assistant backend.

Importing this package applies the offline runtime policy first, so the flags are in place
before any ML library (transformers, sentence-transformers, chromadb) is imported anywhere.
"""

from pha.netguard import install_from_env
from pha.offline import apply_offline_env

apply_offline_env()
install_from_env()  # PHA_NET_GUARD=1: block and log non-loopback connections (privacy test)

__version__ = "0.1.0"
