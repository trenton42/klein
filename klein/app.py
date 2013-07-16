"""
Applications are great.  Lets have more of them.
"""
import sys

from functools import wraps

from werkzeug.routing import Map, Rule

from twisted.python import log
from twisted.python.components import registerAdapter

from twisted.web.server import Site, Request, NOT_DONE_YET
from twisted.internet import reactor

from zope.interface import implements

from klein.resource import KleinResource
from klein.interfaces import IKleinRequest

__all__ = ['Klein', 'run', 'route', 'routeUrl', 'redirect', 'resource', 'addFactory']


class KleinRequest(object):
    implements(IKleinRequest)

    def __init__(self, request):
        self.branch_segments = ['']
        self.mapper = None

    def url_for(self, *args, **kwargs):
        return self.mapper.build(*args, **kwargs)


registerAdapter(KleinRequest, Request, IKleinRequest)


class Klein(object):
    """
    L{Klein} is an object which is responsible for maintaining the routing
    configuration of our application.

    @ivar _url_map: A C{werkzeug.routing.Map} object which will be used for
        routing resolution.
    @ivar _endpoints: A C{dict} mapping endpoint names to handler functions.
    """

    def __init__(self):
        self._url_map = Map()
        self._endpoints = {}
        self._request_handlers = []
        self.factories = []

    @property
    def url_map(self):
        """
        Read only property exposing L{Klein._url_map}.
        """
        return self._url_map

    @property
    def endpoints(self):
        """
        Read only property exposing L{Klein._endpoints}.
        """
        return self._endpoints

    def resource(self):
        """
        Return an L{IResource} which suitably wraps this app.

        @returns: An L{IResource}
        """

        return KleinResource(self)

    def route(self, url, *args, **kwargs):
        """
        Add a new handler for C{url} passing C{args} and C{kwargs} directly to
        C{werkzeug.routing.Rule}.  The handler function will be passed at least
        one argument an L{twisted.web.server.Request} and any keyword arguments
        taken from the C{url} pattern.

        ::
            @app.route("/")
            def index(request):
                return "Hello"

        @param url: A werkzeug URL pattern given to C{werkzeug.routing.Rule}.
        @type url: str

        @returns: decorated handler function.
        """
        def deco(f):
            kwargs.setdefault('endpoint', f.__name__)
            if url.endswith('/'):
                branchKwargs = kwargs.copy()
                branchKwargs['endpoint'] = branchKwargs['endpoint'] + '_branch'

                @wraps(f)
                def branch_f(request, *a, **kw):
                    IKleinRequest(request).branch_segments = kw.pop('__rest__', '').split('/')
                    return f(request, *a, **kw)

                self._endpoints[branchKwargs['endpoint']] = branch_f
                self._url_map.add(Rule(url + '<path:__rest__>', *args, **branchKwargs))

            self._endpoints[kwargs['endpoint']] = f
            self._url_map.add(Rule(url, *args, **kwargs))
            return f

        return deco

    def routeUrl(self, url, func, *args, **kwargs):
        """
        A non-decorator method for route.

        ::
            def index(request):
                return "Hello"

            app.routeUrl("/", index)
        """

        deco = self.route(url, *args, **kwargs)
        deco(func)

    def addRequestHandler(self, func):
        """
        Add a function to be called before the url handler to do
        something with the request (e.g. Session initialization).
        """
        self._request_handlers.append(func)

    def redirect(self, request, url):
        """
        Redirct to C{url}.

        ::
            @app.route("/")
            def index(request):
                return app.redirect(request, "/somewhere_else")

        @param request: The request passed from the calling function
        @type request: L{twisted.web.server.Request}

        @param url: A url to redirect to.
        @type url: str

        @returns: twisted.web.server.NOT_DONE_YET
        """

        request.redirect(url)
        request.finish()
        return NOT_DONE_YET

    def addFactory(self, port, factory):
        """
        Add another service to listen on C{port} using the factory C{factory}

        @param port: The TCP port to accept HTTP requests on
        @type port: int

        @param factory: The factory that will handle connections
        @type factory: factory instance
        """
        self.factories.append((port, factory))

    def run(self, host, port, logFile=None):
        """
        Run a minimal twisted.web server on the specified C{port}, bound to the
        interface specified by C{host} and logging to C{logFile}.

        This function will run the default reactor for your platform and so
        will block the main thread of your application.  It should be the last
        thing your klein application does.

        @param host: The hostname or IP address to bind the listening socket
            to.  "0.0.0.0" will allow you to listen on all interfaces, and
            "127.0.0.1" will allow you to listen on just the loopback interface.
        @type host: str

        @param port: The TCP port to accept HTTP requests on.
        @type port: int

        @param logFile: The file object to log to, by default C{sys.stdout}
        @type logFile: file object
        """
        if logFile is None:
            logFile = sys.stdout

        log.startLogging(logFile)
        reactor.listenTCP(port, Site(self.resource()), interface=host)
        print '*' * 10, 'incoming!', self.factories
        for i in self.factories:
            print 'listening on ', i[0]
            reactor.listenTCP(*i, interface=host)
        reactor.run()


_globalKleinApp = Klein()

route = _globalKleinApp.route
run = _globalKleinApp.run
resource = _globalKleinApp.resource
addFactory = _globalKleinApp.addFactory
routeUrl = _globalKleinApp.routeUrl
redirect = _globalKleinApp.redirect
addRequestHandler = _globalKleinApp.addRequestHandler
