## Overly - the most overly configurable test http/s server this side of the moon.

### Huh?

If you've ever found yourself wanting a test http/s server that you can do the weirdest imaginable things with, overly is for you.

Let's start simple. Say we want to emulate the well known ``/get`` endpoint at httpbin.org, and stick it on a unit/pytest.
We use ``overly.Server`` as a decorator, passing it a series of steps to do when it gets a request. The decorator injects the server object in to the test, kinda like a fixture.

```python
from overly import Server, send_request_as_json, finish

test_loc = ("localhost", 25001)

@Server(test_loc, steps=[send_request_as_json, finish])
def test_request_get(server):
    r = requests.get(server.http_test_url, data='wat')
    assert r.status_code == 200
    assert r.json()['body'] == 'wat'

# The response looks like:
# {
#     'http_version': '1.1',
#     'method': 'POST',
#     'target': '/',
#     'path': '/',
#     'headers': [
#         ['host', 'localhost:25001'],
#         ['connection', 'keep-alive'],
#         ['accept-encoding', 'gzip, deflate'],
#         ['accept', '*/*'],
#         ['content-length', '3'],
#         ['user-agent', 'python-asks/2.2.0'],
#         ['content-type', 'text/plain']
#     ]
#     'body': 'wat'
# }
```

Simples! Now Let's Get Weird.

Want to see if your client will handle a redirect from ``https://example.com``, to ``https://example.com/doowap``, that returns a 404 page that's eight gigabytes, but the server only starts sending data 43 seconds later and kills the socket before finishing, just for kicks? We'll enforce the request order too so we don't accidentally write our tests to miss the redirection case, and skip the first redirect. Alrighty then:

```python
from functools import partial

from overly import (
    Server,
    ssl_socket_wrapper,
    HttpMethods,
    send_303m,
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
