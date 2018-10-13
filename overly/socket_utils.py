__all__ = ["default_socket_factory", "default_socket_wrapper", "ssl_socket_wrapper"]

import os
import socket
import ssl

from contextlib import closing

_HERE = os.path.dirname(__file__)
_DEFAULT_SERVER_CERT = os.path.join(_HERE, "default_server_cert.pem")
_DEFAULT_SERVER_KEY = os.path.join(_HERE, "default_server_key.pem")


def default_socket_factory():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return sock


# ----------------
# Socket wrappers
# ----------------


default_socket_wrapper = closing


def ssl_socket_wrapper(sock):
    return ssl.wrap_socket(
        sock,
        certfile=_DEFAULT_SERVER_CERT,
        keyfile=_DEFAULT_SERVER_KEY,
        server_side=True,
    )
