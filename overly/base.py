import time
import socket
import h11

from threading import Thread, BoundedSemaphore

from .errors import HandledError

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def default_socket_factory():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return s


class Server(Thread):
    def __init__(
        self,
        location,
        *,
        max_requests=1,
        max_concurrency=9999,
        listen_count=5,
        socket_factory=default_socket_factory,
        steps=None,
    ):
        super().__init__()
        self.location = location
        self.host = location[0]
        self.port = location[1]

        self.max_requests = max_requests
        self.requests_count = 0
        self.sema = BoundedSemaphore(max_concurrency)
        self.listen_count = listen_count
        self.socket_factory = socket_factory

        self.steps = steps

        self.http_test_url = "http://{}:{}".format(location[0], str(location[1]))
        self.https_test_url = "https://{}:{}".format(location[0], str(location[1]))

        # For use by builtin steps
        self.request = None

    def run(self):
        self.launch()

    def launch(self):
        s = self.socket_factory()
        s.bind(self.location)
        s.listen(self.listen_count)
        while self.requests_count < self.max_requests:
            with self.sema:
                logger.info("Listening...")
                sock, _ = s.accept()
                self.requests_count += 1
                ClientHandler(sock, self.steps).start()

    def __call__(self, func):
        def inner(*args, **kwargs):
            self.start()
            return func(self, *args, **kwargs)

        return inner


class ClientHandler(Thread):
    def __init__(self, sock, steps=None):
        super().__init__()
        self.conn = h11.Connection(our_role=h11.SERVER)
        self.sock = sock
        self.steps = steps

    def run(self):
        for step in self.steps:
            try:
                logger.info("Step: {}".format(step.__name__))
            except AttributeError:
                logger.info("Step: {}".format(step.func.__name__))
            try:
                step(self)
            except HandledError:
                ...

        self.sock.close()
        logger.info("Completed")

    def http_next_event(self):
        while True:
            event = self.conn.next_event()
            if event is h11.NEED_DATA:
                self.conn.receive_data(self.sock.recv(2048))
                continue
            return event

    def http_send(self, *events):
        for event in events:
            data = self.conn.send(event)
            if data is not None:
                self.sock.sendall(data)
