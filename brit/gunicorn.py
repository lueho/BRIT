"""Gunicorn worker customisations for the Heroku deployment."""

from gunicorn.workers.gthread import ThreadWorker


class SocketTimeoutThreadWorker(ThreadWorker):
    """gthread worker that bounds how long a single socket operation may block.

    The gthread main loop keeps heartbeating while its threads serve requests,
    so the worker timeout never fires for a response write that blocks forever
    on a client that stops reading: every thread parks in sendall and no new
    request is served. Setting a socket timeout after handle() has restored
    blocking mode, before WSGI request/response I/O, turns that park into a
    socket.timeout so the thread is freed.

    This bounds idle socket operations, such as a response write the client is
    not draining; it is not a deadline on view processing time.
    """

    socket_timeout = 10  # seconds

    def handle_request(self, req, conn):
        conn.sock.settimeout(self.socket_timeout)
        try:
            return super().handle_request(req, conn)
        except TimeoutError:
            # A timed-out response is already truncated; closing here skips
            # the main loop's graceful-close drain on the dead socket.
            conn.close()
            raise
