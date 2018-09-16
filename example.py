from overly import Server, receive_request, send_404, delay

if __name__ == '__main__':
	print('DELAY IS', delay)
	Server(
		('localhost', 25001),
		max_connections=10,
		max_concurrency=1,
		steps=[
			receive_request,
			delay(1),
			send_404
		]
	).start()
