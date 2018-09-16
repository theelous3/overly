import h11

import time
from functools import partial

states = [
	h11.IDLE,
	h11.SEND_RESPONSE,
	h11.SEND_BODY,
	h11.DONE,
	h11.MUST_CLOSE,
	h11.CLOSED,
	h11.MIGHT_SWITCH_PROTOCOL,
	h11.SWITCHED_PROTOCOL,
	h11.ERROR
]

INTERLOCUTORS = [
	h11.CLIENT,
	h11.SERVER
]


def receive_request(client_handler):
	return client_handler.http_next_event()


def delay(t=0):
	def delay_(t, *_):
			time.sleep(t)
	return partial(delay_, t)


def send_404(client_handler, data=None):
	client_handler.http_send(
        h11.Response(
        	status_code=404,
            http_version=b'1.1',
            reason=b'NOT FOUND',
            headers=[('connection', 'close')]
        )
	)

	client_handler.http_send(
        h11.Data(data=data or b'404')
	)

	client_handler.http_send(
        h11.EndOfMessage()
	)
