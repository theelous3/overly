import time
import socket
import h11

from threading import Thread, BoundedSemaphore

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def default_socket_factory():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return s


class Server:
    def __init__(
        self,
        location,
        *,
        max_connections=float("inf"),
        max_concurrency=float("inf"),
        listen_count=5,
        socket_factory=default_socket_factory,
        steps=None
    ):
        self.location = location
        self.host = location[0]
        self.port = location[1]

        self.max_connections = max_connections
        self.max_connections_count = 0
        self.sema = BoundedSemaphore(max_concurrency)
        self.listen_count = listen_count
        self.socket_factory = socket_factory

        self.steps = steps

    def start(self):
        s = self.socket_factory()
        s.bind(self.location)
        s.listen(self.listen_count)
        while self.max_connections_count < self.max_connections:
            with self.sema:
                logger.info("Listening...")
                sock, _ = s.accept()
                self.max_connections_count += 1
                ClientHandler(sock, self.steps).start()


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
            step(self)

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
