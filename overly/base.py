from typing import Callable, Generator, Tuple

from threading import Thread, BoundedSemaphore
from queue import Queue

from select import poll
from socket import socket

from collections.abc import Sequence
from collections import deque

import h11

from .socket_utils import default_socket_factory, default_socket_wrapper
from .constants import HttpMethods, PollMaskGroups
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
        sock_timeout=1,
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
        self.queue = Queue()
        self.listen_count = listen_count

        self.socket_factory = socket_factory
        self.socket_wrapper = socket_wrapper

        self.steps = deque(steps)
        self.ordered_steps = ordered_steps

        # This could probably do with a little bit more inspection, for the use of
        # more standard uris.
        self.http_test_url = "http://{}:{}".format(location[0], str(location[1]))
        self.https_test_url = "https://{}:{}".format(location[0], str(location[1]))

        # socket queueing
        self.sock_timeout = sock_timeout
        self.server_sock = None
        self.socket_manager = None
        self.socket_handling_sema = BoundedSemaphore()

        # This flag is set true upon either the max requests being reached, or
        # the decorated func completing / raising an exception. This is so threads
        # can kill themselves in case something weird happens, so we don't hang.
        # Thankfully all threads are using non-blocking ops, so this works :)
        self.kill_threads = False

    def run(self):
        s = self.socket_factory()
        s.bind(self.location)
        s.listen(self.listen_count)
        s.settimeout(self.sock_timeout)

        with self.socket_wrapper(s) as s:

            self.server_sock = s
            self.socket_manager = SocketManager(self)

            logger.info("Listening...")

            while self.requests_count < self.max_requests:

                if self.kill_threads:
                    raise SystemExit("Client finished before max requests.")

                with self.sema:

                    for sock, prefetched_data in self.socket_manager.get_socks():
                        self.queue.put(1)
                        ClientHandler(
                            self,
                            sock,
                            self.http_test_url,
                            self.https_test_url,
                            steps=self.fetch_steps(),
                            prefetched_data=prefetched_data,
                        ).start()

                        self.requests_count += 1

        self.queue.join()
        logger.info("Server signaling to kill client threads.")
        self.kill_threads = True

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

    def __call__(self, func: Callable) -> Callable:
        """
        Allows using Server as a decorator, starting its self in a new thread
        and running its wrappee.
        """

        def inner(*args, **kwargs):
            self.start()
            try:
                result = func(self, *args, **kwargs)
                return result
            finally:
                logger.info("Decorator exit signaling to kill client threads.")
                self.kill_threads = True

        return inner


class SocketManager:
    """
    Handles getting new client sockets, and registered sockets making requests.
    """

    def __init__(self, server: Server):
        self.server = server

        self.server_sock_fileno = server.server_sock.fileno()

        self.socket_filenos = {}
        self.poller = poll()
        self.register_sock(self.server.server_sock)

    def get_socks(self) -> Generator[Tuple[(socket, bytes)], None, None]:
        """
        Get registered socks that are active and sending data, or
        new clients coming in from the server's listening sock.
        """
        with self.server.socket_handling_sema:
            for sock, prefetched_data in self.get_readable_socks():
                try:
                    self.unregister_sock(sock)
                except KeyError:
                    # Already unregistered, or never registered.
                    ...
                yield sock, prefetched_data

    def get_readable_socks(self) -> Generator[Tuple[(socket, bytes)], None, None]:
        """
        Get any registered sockets the OS says are read/writeable.
        Test their state, junking ones we don't like and yielding out
        ones we do like.
        """
        junk_keepalive_socks = []

        for fileno, state in self.poller.poll(0.1):

            if fileno == self.server_sock_fileno:
                if state in PollMaskGroups.READ_WRITE_SIMPLE:
                    new_client, _ = self.server.server_sock.accept()
                    logger.info("New client request.")
                    yield new_client, None

            elif state in PollMaskGroups.READ_WRITES:
                sock = self.socket_filenos[fileno]
                data = sock.recv(1)

                # test for liveliness
                if data == b"":
                    junk_keepalive_socks.append(sock)
                else:
                    logger.info("Keepalive request.")
                    yield sock, data

            elif state in PollMaskGroups.WRITE_SIMPLE:
                # TODO Configurable max lifetime for sockets.
                ...

            elif state in PollMaskGroups.BADS:
                junk_keepalive_socks.append(fileno)

            else:
                raise RuntimeError("Unsupported socket poll mask.")

        self.remove_junk_socks(junk_keepalive_socks)

    def remove_junk_socks(self, junk_socks: [int]) -> None:
        """
        Unregister and throw away smelly socks.
        """
        for fileno in junk_socks:
            try:
                sock = self.socket_filenos[fileno]
                self.unregister_sock(sock)
                sock.close()
                logger.info("Junked {}".format(fileno))
            except KeyError:
                ...

    def register_sock(self, sock: socket) -> None:
        """
        Register the given sock with the polling object, and internal dict.
        """
        self.poller.register(sock)
        self.socket_filenos[sock.fileno()] = sock

    def unregister_sock(self, sock: socket) -> None:
        """
        Unregister the given sock with the polling object, and internal dict.
        """
        fileno = sock.fileno()
        self.poller.unregister(fileno)
        del self.socket_filenos[fileno]


class ClientHandler(Thread):
    def __init__(
        self,
        server,
        sock,
        http_test_url,
        https_test_url,
        *,
        steps=None,
        prefetched_data=None,
    ):
        super().__init__()
        self.server = server

        self.conn = h11.Connection(our_role=h11.SERVER)
        self.sock = sock
        self.steps = steps

        self.step_map = self._construct_step_map()

        self.http_test_url = http_test_url
        self.https_test_url = https_test_url

        self.prefetched_data = prefetched_data

        # For use by builtin steps
        self.request = None
        self.request_body = b""

    def run(self):
        self.server.queue.get()
        self.receive_request()

        self.get_steps()

        try:
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
                    # in cases where we do not respond on time etc. (which would be
                    # intentional).
                    # This may be a bad idea. We'll see.
                    ...
                except EndSteps:
                    # This is a control flow exception which indicates that we
                    # want to end the client as soon as possible.
                    ...
            else:
                with self.server.socket_handling_sema:
                    if self.detect_keepalive():
                        self.server.socket_manager.register_sock(self.sock)
                        logger.info("Completed. Connection kept alive.")
                    else:
                        self.sock.close()
                        logger.info("Completed. Connection closed.")
        finally:
            self.server.queue.task_done()

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
        If there is a step map, pull the steps for the current request
        from the mapping. Steps are mapped by tuple(HttpMethod, uri).

        Sets self.steps equal to the found steps from the mapping.

        If there is no step map, do nothing.
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
            if self.server.kill_threads:
                raise SystemExit
            event = self.conn.next_event()
            if event is h11.NEED_DATA:
                if self.prefetched_data is not None:
                    data = self.prefetched_data + self.sock.recv(2048)
                    self.prefetched_data = None
                else:
                    data = self.sock.recv(2048)
                self.conn.receive_data(data)
                continue
            return event

    def http_send(self, *events):
        for event in events:
            data = self.conn.send(event)
            if data is not None:
                self.sock.sendall(data)
