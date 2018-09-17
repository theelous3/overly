from functools import partial

from overly import Server, receive_request, send_404, delay, send_request_as_json

if __name__ == "__main__":
    Server(
        ("localhost", 25001),
        max_connections=1,
        max_concurrency=1,
        steps=[receive_request, delay(2), send_request_as_json],
    ).start()
    Server(
        ("localhost", 25001),
        max_connections=1,
        max_concurrency=1,
        steps=[receive_request, partial(send_404, data=b"Custom 404 page")],
    ).start()
