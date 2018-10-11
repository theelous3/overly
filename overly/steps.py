# TODO
# 1. Add a way to nicely override automatic request getting for
#    partials, headers only etc.
# 2. Add a way to config headers per steps set, keep-alive etc.


import h11

import time
import json
from functools import partial

from .errors import EndSteps

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --------------
# Response Endings
# --------------


def end_and_close(client_handler):
    client_handler.http_send(h11.EndOfMessage())
    client_handler.http_send(h11.ConnectionClosed())


def just_close(client_handler):
    client_handler.http_send(h11.ConnectionClosed())


def just_end(client_handler):
    client_handler.http_send(h11.EndOfMessage())


def just_kill():
    raise EndSteps


# ---------------------
# 200 <= method <= 299
# ---------------------


def send_request_as_json(client_handler, headers=None):
    response_data = _prepare_request_as_json(client_handler)

    response_headers = [
        ("connection", "close"),
        add_content_len_header(response_data),
        ("content-type", "application/json"),
    ]

    if headers is not None:
        response_headers = _add_external_headers(response_headers, headers)

    client_handler.http_send(
        h11.Response(
            status_code=200, http_version=b"1.1", reason=b"OK", headers=response_headers
        )
    )

    client_handler.http_send(h11.Data(data=_prepare_request_as_json(client_handler)))


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
    data.update({"body": client_handler.request_body.decode()})
    return json.dumps(data).encode()


def send_200(client_handler, headers=None data=None, delay_body=None):
    response_headers = [("connection", "close")]

    if headers is not None:
        response_headers = _add_external_headers(response_headers, headers)

    client_handler.http_send(
        h11.Response(
            status_code=200,
            http_version=b"1.1",
            reason=b"OK",
            headers=response_headers,
        )
    )

    if delay_body is not None:
        logger.info("Delaying body by {} seconds.".format(delay_body))
        time.sleep(delay_body)

    client_handler.http_send(h11.Data(data=data or b"200"))


def send_204(client_handler, headers=None, data=None):
    response_headers = [("connection", "close")]

    if headers is not None:
        response_headers = _add_external_headers(response_headers, headers)

    client_handler.http_send(
        h11.Response(
            status_code=204,
            http_version=b"1.1",
            reason=b"NO CONTENT",
            headers=response_headers,
        )
    )

    client_handler.http_send(h11.Data(data=data or b""))


# ---------------------
# 400 <= method <= 499
# ---------------------


def send_400(client_handler, headers=None, data=None):
    response_headers = [("connection", "close")]

    if headers is not None:
        response_headers = _add_external_headers(response_headers, headers)

    client_handler.http_send(
        h11.Response(
            status_code=400,
            http_version=b"1.1",
            reason=b"BAD REQUEST",
            headers=response_headers,
        )
    )

    client_handler.http_send(h11.Data(data=data or b"400"))


def send_403(client_handler, headers=None, data=None):
    response_headers = [("connection", "close"), add_content_len_header(body)]

    if headers is not None:
        response_headers = _add_external_headers(response_headers, headers)

    body = data or b"404"

    client_handler.http_send(
        h11.Response(
            status_code=403,
            http_version=b"1.1",
            reason=b"FORBIDDEN",
            headers=response_headers,
        )
    )

    client_handler.http_send(h11.Data(data=data or b"403"))


def send_404(client_handler, data=None):
    response_headers = [("connection", "close"), add_content_len_header(body)]

    if headers is not None:
        response_headers = _add_external_headers(response_headers, headers)

    body = data or b"404"

    client_handler.http_send(
        h11.Response(
            status_code=404,
            http_version=b"1.1",
            reason=b"NOT FOUND",
            headers=response_headers,
        )
    )

    client_handler.http_send(h11.Data(data=body))


def send_405(client_handler, headers=None, data=None):
    response_headers = [("connection", "close"), add_content_len_header(body)]

    if headers is not None:
        response_headers = _add_external_headers(response_headers, headers)

    body = data or b"404"

    client_handler.http_send(
        h11.Response(
            status_code=405,
            http_version=b"1.1",
            reason=b"METHOD NOT ALLOWED",
            headers=response_headers,
        )
    )

    client_handler.http_send(h11.Data(data=data or b"405"))


# ---------------------
# 500 <= method <= 599
# ---------------------


def send_500(client_handler, headers=None, data=None):
    response_headers = [("connection", "close"), add_content_len_header(body)]

    if headers is not None:
        response_headers = _add_external_headers(response_headers, headers)

    body = data or b"404"

    client_handler.http_send(
        h11.Response(
            status_code=500,
            http_version=b"1.1",
            reason=b"INTERNAL SERVER ERROR",
            headers=response_headers,
        )
    )

    client_handler.http_send(h11.Data(data=data or b"I'm pretending to be broken >:D"))


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
            client_handler.request_body += event.data

    client_handler.request = request


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


def add_content_len_header(body):
    if hasattr(body, "encode"):
        raise TypeError("content-length must be calculated from bytes-like object")
    return ("content-length", str(len(body).encode()))


#---------------
# Internal utils
#---------------

def _add_external_headers(internal_headers, external_headers):
    new_headers = []

    e_keys = [e_key for e_key, _ in external_headers]

    for i_key, i_value in internal_headers:
        if i_key not in e_keys:
            new_headers.append((i_key, i_value))

    new_headers.extend(external_headers)

    return new_headers