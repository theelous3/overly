# TODO
# 1. Add a way to nicely override automatic request getting for
#    partials, headers only etc.
# 2. Add a way to config headers per steps set, keep-alive etc.


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


def send_200(client_handler, data=None):
    client_handler.http_send(
        h11.Response(
            status_code=200,
            http_version=b"1.1",
            reason=b"OK",
            headers=[("connection", "close")],
        )
    )

    client_handler.http_send(h11.Data(data=data or b"200"))

    client_handler.http_send(h11.EndOfMessage())
    client_handler.http_send(h11.ConnectionClosed())


def send_204(client_handler, data=None):
    client_handler.http_send(
        h11.Response(
            status_code=204,
            http_version=b"1.1",
            reason=b"NO CONTENT",
            headers=[("connection", "close")],
        )
    )

    client_handler.http_send(h11.Data(data=data or b""))

    client_handler.http_send(h11.EndOfMessage())
    client_handler.http_send(h11.ConnectionClosed())


# ---------------------
# 400 <= method <= 499
# ---------------------


def send_400(client_handler, data=None):
    client_handler.http_send(
        h11.Response(
            status_code=400,
            http_version=b"1.1",
            reason=b"BAD REQUEST",
            headers=[("connection", "close")],
        )
    )

    client_handler.http_send(h11.Data(data=data or b"400"))

    client_handler.http_send(h11.EndOfMessage())
    client_handler.http_send(h11.ConnectionClosed())


def send_403(client_handler, data=None):
    client_handler.http_send(
        h11.Response(
            status_code=403,
            http_version=b"1.1",
            reason=b"FORBIDDEN",
            headers=[("connection", "close")],
        )
    )

    client_handler.http_send(h11.Data(data=data or b"403"))

    client_handler.http_send(h11.EndOfMessage())
    client_handler.http_send(h11.ConnectionClosed())


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


# ---------------------
# 500 <= method <= 599
# ---------------------


def send_500(client_handler, data=None):
    client_handler.http_send(
        h11.Response(
            status_code=500,
            http_version=b"1.1",
            reason=b"INTERNAL SERVER ERROR",
            headers=[("connection", "close")],
        )
    )

    client_handler.http_send(h11.Data(data=data or b"I'm pretending to be broken >:D"))

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
