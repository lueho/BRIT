"""Gunicorn worker customisations for the Heroku deployment."""

from gunicorn.workers.gthread import TConn, ThreadWorker


class _TimeoutClosingParser:
    """Delegating parser that closes the connection when header reads time out.

    Closing in the request thread skips the main loop's graceful-close drain,
    which would otherwise wait on the stalled peer.
    """

    def __init__(self, parser, conn):
        self._parser = parser
        self._conn = conn

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return next(self._parser)
        except TimeoutError:
            self._conn.close()
            raise

    def __getattr__(self, name):
        return getattr(self._parser, name)


class SocketTimeoutConn(TConn):
    """gthread connection whose blocking socket operations time out."""

    socket_timeout = None

    def init(self):
        # ThreadWorker.handle() restores plain blocking mode before every
        # init() call, so the timeout is re-applied before header parsing.
        super().init()
        self.sock.settimeout(self.socket_timeout)
        if not self.is_http2 and not isinstance(self.parser, _TimeoutClosingParser):
            self.parser = _TimeoutClosingParser(self.parser, self)

    def close(self, graceful=False):
        # A timed-out socket was already closed by its request thread; the
        # main loop's follow-up close must not touch the dead descriptor.
        if self.sock.fileno() == -1:
            return
        super().close(graceful=graceful)


class SocketTimeoutThreadWorker(ThreadWorker):
    """gthread worker that bounds how long a single socket operation may block.

    The gthread main loop keeps heartbeating while its threads serve requests,
    so the worker timeout never fires for a thread parked on a stalled client:
    one that sends partial request headers or stops reading its response.
    Four such clients occupy every thread and no new request is served.
    Applying a socket timeout once handle() has switched the connection to
    blocking mode, before header parsing and WSGI I/O, turns that park into a
    socket.timeout so the thread is freed.

    This bounds idle socket operations, such as a response write the client is
    not draining; it is not a deadline on view processing time.
    """

    socket_timeout = 10  # seconds

    def handle(self, conn):
        if not isinstance(conn, SocketTimeoutConn):
            # gthread builds plain TConn objects in accept(); upgrade them
            # here instead of copying accept().
            conn.__class__ = SocketTimeoutConn
        conn.socket_timeout = self.socket_timeout
        return super().handle(conn)

    def handle_request(self, req, conn):
        try:
            return super().handle_request(req, conn)
        except TimeoutError:
            # A timed-out response is already truncated; closing here skips
            # the main loop's graceful-close drain on the dead socket.
            conn.close()
            raise
