from functools import partial

from overly import (
    Server,
    ssl_socket_wrapper,
    send_200,
    send_204,
    send_303,
    send_404,
    delay,
    send_request_as_json,
    finish,
    HttpMethods,
)

import requests


if __name__ == "__main__":
    # Give the servers a location
    test_loc = ("localhost", 25001)

    # Wait one second and return the response as json

    Server(test_loc, steps=[send_404, finish]).run()

    # # HTTPS, same as above

    # Server(
    #     test_loc,
    #     steps=[delay(1), send_request_as_json, finish],
    #     ssl_socket_wrapper=ssl_socket_wrapper,
    # ).run()

    # # # Return a 404 with a custom body

    # Server(test_loc, steps=[partial(send_404, data=b"Custom 404 page"), finish]).run()

    # # # Return a 200 with a delayed custom body
    # # # Currently sending keep-alive for testing

    # Server(
    #     test_loc,
    #     steps=[
    #         partial(
    #             send_200,
    #             data=b"Custom 200 page",
    #             delay_body=1,
    #             headers=[("connection", "keep-alive")],
    #         ),
    #         finish,
    #     ],
    # ).run()

    # # # Define multiple endpoints and / or methods

    # Server(
    #     test_loc,
    #     max_requests=2,
    #     steps=[
    #         [(HttpMethods.GET, "/missing_page"), send_404, finish],
    #         [(HttpMethods.POST, "/"), send_204, finish],
    #     ],
    # ).run()

    # # # Enfore order on the requests for redirection.
    # # # Doesn't support keep-alive I think

    # Server(
    #     test_loc,
    #     max_requests=2,
    #     steps=[
    #         [(HttpMethods.GET, "/missing_page"), send_303, finish],
    #         [(HttpMethods.GET, "/"), send_request_as_json, finish],
    #     ],
    #     ordered_steps=True,
    # ).run()

    # # Use Server as a decorator on a test!

    @Server(test_loc, steps=[send_404, finish])
    def test_request_get_404(server):
        r = requests.get(server.http_test_url)
        assert r.status_code == 404

    # test_request_get_404()
