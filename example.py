from functools import partial

from overly import (
    Server,
    send_200,
    send_204,
    send_404,
    delay,
    send_request_as_json,
    end_and_close,
    HttpMethods,
)

import requests


if __name__ == "__main__":
    # Give the servers a location
    test_loc = ("localhost", 25001)

    # # Wait one second and return the response as json
    Server(test_loc, steps=[delay(1), send_request_as_json, end_and_close]).run()

    # # Return a 404 with a custom body
    Server(
        test_loc,
        steps=[partial(send_404, data=b"Custom 404 page" * 30000), end_and_close],
    ).run()

    # Return a 200 with a delayed custom body
    Server(
        test_loc,
        steps=[
            partial(send_200, data=b"Custom 200 page" * 300, delay_body=1),
            end_and_close,
        ],
    ).run()

    # Define multiple endpoints and / or methods
    # I don't think end and close will work here.
    Server(
        test_loc,
        max_requests=2,
        steps=[
            [(HttpMethods.GET, "/missing_page"), send_404],
            [(HttpMethods.POST, "/"), send_204],
        ],
    ).run()

    # Use Server as a decorator on a test!
    print("*" * 15, "Test start", "*" * 15)

    @Server(test_loc, steps=[send_404, end_and_close])
    def test_request_get_404(server):
        r = requests.get(server.http_test_url)
        assert r.status_code == 404

    test_request_get_404()

    print("*" * 15, "Test end", "*" * 15)
