import h11

import time
import json
from functools import partial

from .errors import EndSteps, StepError

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------
# 200 <= method <= 299
# ---------------------


def send_request_as_json(client_handler):
    method_check(client_handler, "GET")
    response_data = _prepare_request_as_json(client_handler)

    response_headers = [
        ("connection", "close"),
        ("content-length", str(len(response_data)).encode()),
        ("content-type", "application/json"),
    ]

    client_handler.http_send(
        h11.Response(
            status_code=200, http_version=b"1.1", reason=b"OK", headers=response_headers
        )
    )

    client_handler.http_send(h11.Data(data=_prepare_request_as_json(client_handler)))

    client_handler.http_send(h11.EndOfMessage())
    client_handler.http_send(h11.ConnectionClosed())


def _prepare_request_as_json(client_handler):
    data = {}
    data.update({"http_version": client_handler.request.http_version.decode()})
    data.update({"method": client_handler.request.method.decode()})
    data.update({"target": client_handler.request.target.decode()})
    data.update(
        {
            "headers": (header.decode(), value.decode())
            for header, value in client_handler.request.headers
        }
    )
    return json.dumps(data).encode()


# 400 <= method <= 499


def send_404(client_handler, data=None):
    client_handler.http_send(
        h11.Response(
            status_code=404,
            http_version=b"1.1",
            reason=b"NOT FOUND",
            headers=[("connection", "close")],
        )
    )

    client_handler.http_send(h11.Data(data=data or b"404"))

    client_handler.http_send(h11.EndOfMessage())
    client_handler.http_send(h11.ConnectionClosed())


def send_405(client_handler, data=None):
    client_handler.http_send(
        h11.Response(
            status_code=405,
            http_version=b"1.1",
            reason=b"METHOD NOT ALLOWED",
            headers=[("connection", "close")],
        )
    )

    client_handler.http_send(h11.Data(data=data or b"405"))

    client_handler.http_send(h11.EndOfMessage())
    client_handler.http_send(h11.ConnectionClosed())


# -------------------------
# implementation modifiers
# -------------------------


def receive_request(client_handler):
    """
    This func is duplicated as a method in ClientHandler.
    It is required for deciding which method and path to act on
    when multiple steps are defined.
    """
    request = client_handler.http_next_event()
    while True:
        event = client_handler.http_next_event()
        if isinstance(event, h11.EndOfMessage):
            break
        elif isinstance(event, h11.Data):
            client_handler.body += event.data

    client_handler.request = request
    print("target", request.target)


def delay(t=0):
    def delay_(t, *_):
        time.sleep(t)

    return partial(delay_, t)


# ------------
# http utils
# ------------


def method_check(client_handler, correct_method):
    if not client_handler.request.method == correct_method.encode():
        send_405(client_handler)
        raise EndSteps
