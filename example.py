from functools import partial

from overly import Server, receive_request, send_404, delay, send_request_as_json

import requests

if __name__ == "__main__":
    # Wait one second and return the response as json
    Server(
        ("localhost", 25001), steps=[receive_request, delay(1), send_request_as_json]
    ).launch()

    # Return a 404 with a custom body
    Server(
        ("localhost", 25001),
        steps=[receive_request, partial(send_404, data=b"Custom 404 page")],
    ).launch()

    # Use Server as a decorator on a test!
    test_loc = ("localhost", 25001)

    @Server(test_loc, steps=[receive_request, send_404])
    def test_request_get_404(server):
        r = requests.get(server.http_test_url)
        assert r.status_code == 404

    test_request_get_404()
