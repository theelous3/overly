from typing import Callable

import time

from threading import Thread, BoundedSemaphore
from queue import Queue, Empty

from select import select
from socket import socket

from collections.abc import Sequence
from collections import deque

import h11

from .socket_utils import default_socket_factory, default_socket_wrapper
from .constants import HttpMethods
from .errors import EndSteps, MalformedStepError

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Server(Thread):
    def __init__(
        self,
        location,
        *,
        max_requests=1,
        max_concurrency=9999,
        listen_count=5,
        socket_factory=default_socket_factory,
        socket_wrapper=default_socket_wrapper,
        steps=None,
        ordered_steps=False,
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
        self.socket_wrapper = socket_wrapper

        self.steps = deque(steps)
        self.ordered_steps = ordered_steps

        self.http_test_url = "http://{}:{}".format(location[0], str(location[1]))
        self.https_test_url = "https://{}:{}".format(location[0], str(location[1]))

        # Keepalive handling
        self.keepalive_socks = []
        self.sessioned_socks_queue = Queue()

    def run(self):
        s = self.socket_factory()
        s.bind(self.location)
        s.listen(self.listen_count)

        with self.socket_wrapper(s) as s:
            while self.requests_count < self.max_requests:
                with self.sema:
                    logger.info("Listening...")

                    if self.keepalive_socks:
                        self.queue_keepalive_socks()

                    try:
                        queued_sock = self.sessioned_socks_queue.get(block=False)
                    except Empty:
                        sock = self.get_new_connection(s)
                        if sock is None:
                            continue
                    else:
                        sock = queued_sock

                    self.requests_count += 1

                    ClientHandler(
                        self,
                        sock,
                        self.http_test_url,
                        self.https_test_url,
                        steps=self.fetch_steps(),
                    ).start()

    def queue_keepalive_socks(self):
        """
        Queue any keepalive socks that are sending new data.
        """
        readable_socks, _, _ = select(self.keepalive_socks, [], [])

        for sock in readable_socks:
            self.sessioned_socks_queue.put(sock)

    def get_new_connection(self, server_sock) -> (socket, str):
        """
        We don't want to block forever waiting on socket.accept as
        there may be keep alive sockets waiting. We poll select instead.
        """
        new_connections, _, _ = select([server_sock], [], [])
        try:
            return new_connections[0].accept()[0]
        except IndexError:
            return None

    def fetch_steps(self) -> list:
        """
        Get either the next step or all steps.
        When the steps are ordered, each is equiv to a full step
        as defined in the most basic case.
        """
        if self.ordered_steps:
            x = [self.steps.popleft()]
            return x

        return self.steps

    def __call__(self, func) -> Callable:
        """
        Allows using Server as a decorator, starting its self in a new thread
        and running its wrappee.
        """

        def inner(*args, **kwargs):
            self.start()
            return func(self, *args, **kwargs)

        return inner


class ClientHandler(Thread):
    def __init__(self, server, sock, http_test_url, https_test_url, *, steps=None):
        super().__init__()
        self.server = server

        self.conn = h11.Connection(our_role=h11.SERVER)
        self.sock = sock
        self.steps = steps

        self.step_map = self._construct_step_map()

        self.http_test_url = http_test_url
        self.https_test_url = https_test_url

        # For use by builtin steps
        self.request = None
        self.request_body = b""

    def run(self):
        self.receive_request()

        keepalive = self.detect_keepalive()

        self.get_steps()

        for step in self.steps:
            try:
                logger.info("Step: {}".format(step.__name__))
            except AttributeError:
                logger.info("Step: {}".format(step.func.__name__))
            try:
                step(self)
            except BrokenPipeError:
                # Currently we suppress the case of trying to send data to the
                # client, but the client has already closed their socket.
                # This is so we do not raise exceptions in the client's tests
                # in cases where we do not respond on time etc.
                # This may be a bad idea. We'll see.
                ...
            except EndSteps:
                ...
        else:
            if keepalive:
                self.server.keepalive_socks.append(self.sock)
                logger.info("Complete. Requeued keepalive sock.")
            else:
                self.sock.close()
                logger.info("Completed")

    def detect_keepalive(self) -> bool:
        """
        Figure out if the client has requested a keep-alive connection.
        """
        return next(
            (
                True
                for header, value in self.request.headers
                if (header, value) == (b"connection", b"keep-alive")
            ),
            False,
        )

    def get_steps(self):
        """
        Pull the steps for the current request from the step_map.
        """
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

    def _construct_step_map(self):
        """
        Create a mapping for each step, where the key is a tuple
        of the method and path, and the value is a list of steps to run.
        """
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
        This method is duplicated as a func in steps.py
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
