import time
import socket

from threading import Thread, BoundedSemaphore
from collections.abc import Sequence

import h11

from .errors import EndSteps, MalformedStepError
from .constants import HttpMethods

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

    def run(self):
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

        self.step_map = self._parse_steps()

        # For use by builtin steps
        self.request = None
        self.request_body = b""

    def run(self):
        self.receive_request()
        if self.step_map is not None:
            try:
                self.steps = self.step_map[
                    (
                        HttpMethods(self.request.method.decode()),
                        self.request.target.decode(),
                    )
                ]
            except KeyError:
                self.sock.close()
                raise MalformedStepError(
                    "Couldn't find matching step "
                    "for metohd {} at target {}".format(
                        self.request.method.decode(), self.request.target.decode()
                    )
                )

        for step in self.steps:
            try:
                logger.info("Step: {}".format(step.__name__))
            except AttributeError:
                logger.info("Step: {}".format(step.func.__name__))
            try:
                step(self)
            except EndSteps:
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

    def _parse_steps(self):
        step_map = {}
        for step in self.steps:
            if isinstance(step, Sequence):
                try:
                    http_method, path = step[0]
                    assert isinstance(http_method, HttpMethods)
                    assert isinstance(path, str)
                except (AssertionError, IndexError, ValueError, TypeError):
                    raise MalformedStepError(
                        "0th elem of multi step sequences "
                        "must be formed: (HttpMethods, str)"
                    )
                step_map[(http_method, path)] = step[1:]

        return step_map or None

    def receive_request(self):
        """
        This mathod is duplicated as a func in steps.py
        It is required for deciding which method and path to act on
        when multiple steps are defined.
        """
        request = self.http_next_event()
        while True:
            event = self.http_next_event()
            if isinstance(event, h11.EndOfMessage):
                break
            elif isinstance(event, h11.Data):
                self.request_body += event.data

        self.request = request
