import os
import socket

import pytest

import pha  # noqa: F401  (import applies the offline policy)
from tests.conftest import OutboundConnectionError


def test_offline_flags_set_on_import():
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    assert os.environ["ANONYMIZED_TELEMETRY"] == "False"


def test_socket_guard_blocks_outbound():
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s,
        pytest.raises(OutboundConnectionError),
    ):
        s.connect(("93.184.215.14", 80))


def test_socket_guard_allows_loopback():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as c:
            c.connect(srv.getsockname())
