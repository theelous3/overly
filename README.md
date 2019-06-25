## Overly - the most overly configurable test http/s server this side of the moon.

### Huh?

If you've ever found yourself wanting a test http/s server that you can do the weirdest imaginable things with, overly is for you.

Let's start simple. Say we want to emulate the well known ``/get`` endpoint at httpbin.org, and stick it on a unit/pytest.
We use ``overly.Server`` as a decorator, passing it a series of steps to do when it gets a request. The decorator injects the server object in to the test, kinda like a fixture.

```python
import requests
from overly import Server, send_request_as_json, finish

@Server(("localhost", 25001), steps=[send_request_as_json, finish])
def test_json_send(server):
    r = requests.post(
        server.http_test_url, json={"key_1": True, "key_2": "cheesestring"}
    )
    pprint(r.json())

# The response is:
#
# 'body': '{"key_1": true, "key_2": "cheesestring"}',
# 'files': [],
# 'forms': [],
# 'headers': [
#     ['host', 'localhost:25001'],
#     ['user-agent', 'python-requests/2.19.1'],
#     ['accept-encoding', 'gzip, deflate'],
#     ['accept', '*/*'],
#     ['connection', 'keep-alive'],
#     ['content-length', '40'],
#     ['content-type', 'application/json']],
# 'http_version': '1.1',
# 'json': [
#     {
#         'json': {'key_1': True, 'key_2': 'cheesestring'}
#     }
# ],
# 'method': 'POST',
# 'path': '/',
# 'target': '/'}
```

Simples! Now Let's Get Weird.

Want to see if your client will handle a redirect from ``https://example.com``, to ``https://example.com/doowap``, that returns a 404 page that's eight gigabytes, but the server only starts sending data 43 seconds later and kills the socket before finishing, just for kicks? We'll enforce the request order too so we don't accidentally write our tests to miss the redirection case, and skip the first redirect. Alrighty then:

```python
from functools import partial

from overly import (
    Server,
    ssl_socket_wrapper,
    HttpMethods,
    send_303,
    send_404,
    delay,
    just_kill
)

test_loc = ("localhost", 25001)

eight_gigs = 1 * (1024 ** 3) * 8)

Server(
    test_loc,
    max_requests=2,
    ordered_steps=True,
    ssl_socket_wrapper=ssl_socket_wrapper,
    steps=[
        [
            (HttpMethods.GET, "/"),
            partial(send_303, headers=("location", "/doowap")),
            finish
        ],
        [
            (HttpMethods.GET, "/doowap"),
            delay(43),
            partial(send_404, data=b"x" * eight_gigs,
            just_kill
        ]
    ]
).run()
```


Bam. The worst 404 page of all time. The above can be used as a decorator, just like before. We can also just run the server with ``Server.run()`` for easy messing about.

As was mentioned, and as you can see, overly is overly configurabe :D All of your bases are covered!

The ``Server`` is concurrent, so you can test all of your weird async / threaded / voodoo clients, with keep-alive support.