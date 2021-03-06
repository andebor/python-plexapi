# -*- coding: utf-8 -*-
import plexapi, requests
from plexapi import TIMEOUT, log, logfilter, utils
from plexapi.exceptions import BadRequest, NotFound, Unauthorized
from plexapi.client import PlexClient
from plexapi.compat import ElementTree
from plexapi.server import PlexServer
from requests.status_codes import _codes as codes
CONFIG = plexapi.CONFIG


class MyPlexAccount(object):
    """ MyPlex account and profile information. The easiest way to build
        this object is by calling the staticmethod :func:`~plexapi.myplex.MyPlexAccount.signin`
        with your username and password. This object represents the data found Account on
        the myplex.tv servers at the url https://plex.tv/users/account.

        Attributes:
            authenticationToken (str): <Unknown>
            certificateVersion (str): <Unknown>
            cloudSyncDevice (str): 
            email (str): Your current Plex email address.
            entitlements (List<str>): List of devices your allowed to use with this account.
            guest (bool): <Unknown>
            home (bool): <Unknown>
            homeSize (int): <Unknown>
            id (str): Your Plex account ID.
            locale (str): Your Plex locale
            mailing_list_status (str): Your current mailing list status.
            maxHomeSize (int): <Unknown>
            queueEmail (str): Email address to add items to your `Watch Later` queue.
            queueUid (str): <Unknown>
            restricted (bool): <Unknown>
            roles: (List<str>) Lit of account roles. Plexpass membership listed here.
            scrobbleTypes (str): Description
            secure (bool): Description
            subscriptionActive (bool): True if your subsctiption is active.
            subscriptionFeatures: (List<str>) List of features allowed on your subscription.
            subscriptionPlan (str): Name of subscription plan.
            subscriptionStatus (str): String representation of `subscriptionActive`.
            thumb (str): URL of your account thumbnail.
            title (str): <Unknown> - Looks like an alias for `username`.
            username (str): Your account username.
            uuid (str): <Unknown>
    """
    BASEURL = 'https://plex.tv/users/account'
    SIGNIN = 'https://my.plexapp.com/users/sign_in.xml'

    def __init__(self, data=None, initpath=None, session=None):
        self._data = data
        self._session = session or requests.Session()
        self.authenticationToken = data.attrib.get('authenticationToken')
        if self.authenticationToken:
            logfilter.add_secret(self.authenticationToken)
        self.certificateVersion = data.attrib.get('certificateVersion')
        self.cloudSyncDevice = data.attrib.get('cloudSyncDevice')
        self.email = data.attrib.get('email')
        self.guest = utils.cast(bool, data.attrib.get('guest'))
        self.home = utils.cast(bool, data.attrib.get('home'))
        self.homeSize = utils.cast(int, data.attrib.get('homeSize'))
        self.id = data.attrib.get('id')
        self.locale = data.attrib.get('locale')
        self.mailing_list_status = data.attrib.get('mailing_list_status')
        self.maxHomeSize = utils.cast(int, data.attrib.get('maxHomeSize'))
        self.queueEmail = data.attrib.get('queueEmail')
        self.queueUid = data.attrib.get('queueUid')
        self.restricted = utils.cast(bool, data.attrib.get('restricted'))
        self.scrobbleTypes = data.attrib.get('scrobbleTypes')
        self.secure = utils.cast(bool, data.attrib.get('secure'))
        self.thumb = data.attrib.get('thumb')
        self.title = data.attrib.get('title')
        self.username = data.attrib.get('username')
        self.uuid = data.attrib.get('uuid')
        # TODO: Fetch missing MyPlexAccount attributes
        self.subscriptionActive = None      # renamed on server
        self.subscriptionStatus = None      # renamed on server
        self.subscriptionPlan = None        # renmaed on server
        self.subscriptionFeatures = None    # renamed on server
        self.roles = None
        self.entitlements = None

    def __repr__(self):
        return '<%s:%s:%s>' % (self.__class__.__name__, self.id, self.username.encode('utf8'))

    def device(self, name):
        """ Returns the :class:`~plexapi.myplex.MyPlexDevice` that matches the name specified.

            Parameters:
                name (str): Name to match against.
        """
        return _findItem(self.devices(), name)

    def devices(self):
        """ Returns a list of all :class:`~plexapi.myplex.MyPlexDevice` objects connected to the server. """
        return _listItems(MyPlexDevice.BASEURL, self.authenticationToken, MyPlexDevice)

    def resources(self):
        """ Returns a list of all :class:`~plexapi.myplex.MyPlexResource` objects connected to the server. """
        return _listItems(MyPlexResource.BASEURL, self.authenticationToken, MyPlexResource)

    def resource(self, name):
        """ Returns the :class:`~plexapi.myplex.MyPlexResource` that matches the name specified.

            Parameters:
                name (str): Name to match against.
        """
        return _findItem(self.resources(), name)

    def users(self):
        """ Returns a list of all :class:`~plexapi.myplex.MyPlexUser` objects connected to your account. """
        return _listItems(MyPlexUser.BASEURL, self.authenticationToken, MyPlexUser)

    def user(self, email):
        """ Returns the :class:`~myplex.MyPlexUser` that matches the email or username specified.

            Parameters:
                email (str): Username or email to match against.
        """
        return _findItem(self.users(), email, ['username', 'email'])

    @classmethod
    def signin(cls, username=None, password=None, session=None):
        """ Returns a new :class:`~myplex.MyPlexAccount` object by connecting to MyPlex with the
            specified username and password. This is essentially logging into MyPlex and often
            the very first entry point to using this API.

            Parameters:
                username (str): Your MyPlex.tv username. If not specified, it will check the config.ini file.
                password (str): Your MyPlex.tv password. If not specified, it will check the config.ini file.

            Raises:
                :class:`~plexapi.exceptions.Unauthorized`: (401) If the username or password are invalid.
                :class:`~plexapi.exceptions.BadRequest`: If any other errors occured not allowing us to log into MyPlex.tv.
        """
        if 'X-Plex-Token' in plexapi.BASE_HEADERS:
            del plexapi.BASE_HEADERS['X-Plex-Token']
        username = username or CONFIG.get('authentication.username')
        password = password or CONFIG.get('authentication.password')
        auth = (username, password)
        log.info('POST %s', cls.SIGNIN)
        sess = session or requests.Session()
        response = sess.post(
            cls.SIGNIN, headers=plexapi.BASE_HEADERS, auth=auth, timeout=TIMEOUT)
        if response.status_code != requests.codes.created:
            codename = codes.get(response.status_code)[0]
            if response.status_code == 401:
                raise Unauthorized('(%s) %s' % (response.status_code, codename))
            raise BadRequest('(%s) %s' % (response.status_code, codename))
        data = ElementTree.fromstring(response.text.encode('utf8'))
        return MyPlexAccount(data, cls.SIGNIN, session=sess)


class MyPlexUser(object):
    """ This object represents non-signed in users such as friends and linked
        accounts. NOTE: This should not be confused with the :class:`~myplex.MyPlexAccount`
        which is your specific account. The raw xml for the data presented here
        can be found at: https://plex.tv/api/users/

        Attributes:
            allowCameraUpload (bool): True if this user can upload images
            allowChannels (bool): True if this user has access to channels
            allowSync (bool): True if this user can sync
            email (str): User's email address (user@gmail.com)
            filterAll (str): Unknown
            filterMovies (str): Unknown
            filterMusic (str): Unknown
            filterPhotos (str): Unknown
            filterTelevision (str): Unknown
            home (bool): Unknown
            id (int): User's Plex account ID.
            protected (False): Unknown (possibly SSL enabled?)
            recommendationsPlaylistId (str): Unknown
            restricted (str): Unknown
            thumb (str): Link to the users avatar
            title (str): Seems to be an aliad for username
            username (str): User's username
    """
    BASEURL = 'https://plex.tv/api/users/'

    def __init__(self, data, initpath=None):
        self._data = data
        self.allowCameraUpload = utils.cast(bool, data.attrib.get('allowCameraUpload'))
        self.allowChannels = utils.cast(bool, data.attrib.get('allowChannels'))
        self.allowSync = utils.cast(bool, data.attrib.get('allowSync'))
        self.email = data.attrib.get('email')
        self.filterAll = data.attrib.get('filterAll')
        self.filterMovies = data.attrib.get('filterMovies')
        self.filterMusic = data.attrib.get('filterMusic')
        self.filterPhotos = data.attrib.get('filterPhotos')
        self.filterTelevision = data.attrib.get('filterTelevision')
        self.home = utils.cast(bool, data.attrib.get('home'))
        self.id = utils.cast(int, data.attrib.get('id'))
        self.protected = utils.cast(bool, data.attrib.get('protected'))
        self.recommendationsPlaylistId = data.attrib.get('recommendationsPlaylistId')
        self.restricted = data.attrib.get('restricted')
        self.thumb = data.attrib.get('thumb')
        self.title = data.attrib.get('title')
        self.username = data.attrib.get('username')

    def __repr__(self):
        return '<%s:%s:%s>' % (self.__class__.__name__, self.id, self.username)


class MyPlexResource(object):
    """ This object represents resources connected to your Plex server that can provide
        content such as Plex Media Servers, iPhone or Android clients, etc. The raw xml
        for the data presented here can be found at: https://plex.tv/api/resources?includeHttps=1

        Attributes:
            accessToken (str): This resources accesstoken.
            clientIdentifier (str): Unique ID for this resource.
            connections (list): List of :class:`~myplex.ResourceConnection` objects
                for this resource.
            createdAt (datetime): Timestamp this resource first connected to your server.
            device (str): Best guess on the type of device this is (PS, iPhone, Linux, etc).
            home (bool): Unknown
            lastSeenAt (datetime): Timestamp this resource last connected.
            name (str): Descriptive name of this resource.
            owned (bool): True if this resource is one of your own (you logged into it).
            platform (str): OS the resource is running (Linux, Windows, Chrome, etc.)
            platformVersion (str): Version of the platform.
            presence (bool): True if the resource is online
            product (str): Plex product (Plex Media Server, Plex for iOS, Plex Web, etc.)
            productVersion (str): Version of the product.
            provides (str): List of services this resource provides (client, server,
                player, pubsub-player, etc.)
            synced (bool): Unknown (possibly True if the resource has synced content?)
    """
    BASEURL = 'https://plex.tv/api/resources?includeHttps=1'

    def __init__(self, data):
        self._data = data
        self.name = data.attrib.get('name')
        self.accessToken = data.attrib.get('accessToken')
        if self.accessToken:
            logfilter.add_secret(self.accessToken)
        self.product = data.attrib.get('product')
        self.productVersion = data.attrib.get('productVersion')
        self.platform = data.attrib.get('platform')
        self.platformVersion = data.attrib.get('platformVersion')
        self.device = data.attrib.get('device')
        self.clientIdentifier = data.attrib.get('clientIdentifier')
        self.createdAt = utils.toDatetime(data.attrib.get('createdAt'))
        self.lastSeenAt = utils.toDatetime(data.attrib.get('lastSeenAt'))
        self.provides = data.attrib.get('provides')
        self.owned = utils.cast(bool, data.attrib.get('owned'))
        self.home = utils.cast(bool, data.attrib.get('home'))
        self.synced = utils.cast(bool, data.attrib.get('synced'))
        self.presence = utils.cast(bool, data.attrib.get('presence'))
        self.connections = [ResourceConnection(elem) for elem in data if elem.tag == 'Connection']

    def __repr__(self):
        return '<%s:%s>' % (self.__class__.__name__, self.name.encode('utf8'))

    def connect(self, ssl=None):
        """ Returns a new :class:`~server.PlexServer` object. Often times there is more than
            one address specified for a server or client. This function will prioritize local
            connections before remote and HTTPS before HTTP. After trying to connect to all
            available addresses for this resource and assuming at least one connection was
            successful, the PlexServer object is built and returned.

            Parameters:
                ssl (optional): Set True to only connect to HTTPS connections. Set False to
                    only connect to HTTP connections. Set None (default) to connect to any
                    HTTP or HTTPS connection.

            Raises:
                :class:`~plexapi.exceptions.NotFound`: When unable to connect to any addresses for this resource.
        """
        # Sort connections from (https, local) to (http, remote)
        # Only check non-local connections unless we own the resource
        forcelocal = lambda c: self.owned or c.local
        connections = sorted(self.connections, key=lambda c: c.local, reverse=True)
        https = [c.uri for c in self.connections if forcelocal(c)]
        http = [c.httpuri for c in self.connections if forcelocal(c)]
        # Force ssl, no ssl, or any (default)
        if ssl is True: connections = https
        elif ssl is False: connections = http
        else: connections = https + http
        # Try connecting to all known resource connections in parellel, but
        # only return the first server (in order) that provides a response.
        listargs = [[c] for c in connections]
        results = utils.threaded(self._connect, listargs)
        # At this point we have a list of result tuples containing (url, token, PlexServer)
        # or (url, token, None) in the case a connection could not be
        # established.
        for url, token, result in results:
            okerr = 'OK' if result else 'ERR'
            log.info('Testing resource connection: %s?X-Plex-Token=%s %s', url, token, okerr)
        results = [r[2] for r in results if r and r[2] is not None]
        if not results:
            raise NotFound('Unable to connect to resource: %s' % self.name)
        log.info('Connecting to server: %s?X-Plex-Token=%s', results[0].baseurl, results[0].token)
        return results[0]

    def _connect(self, url, results, i):
        try:
            results[i] = (url, self.accessToken, PlexServer(url, self.accessToken))
        except NotFound:
            results[i] = (url, self.accessToken, None)


class ResourceConnection(object):
    """ Represents a Resource Connection object found within the
        :class:`~myplex.MyPlexResource` objects.

        Attributes:
            address (str): Local IP address
            httpuri (str): Full local address
            local (bool): True if local
            port (int): 32400
            protocol (str): HTTP or HTTPS
            uri (str): External address
    """
    def __init__(self, data):
        self._data = data
        self.protocol = data.attrib.get('protocol')
        self.address = data.attrib.get('address')
        self.port = utils.cast(int, data.attrib.get('port'))
        self.uri = data.attrib.get('uri')
        self.local = utils.cast(bool, data.attrib.get('local'))
        self.httpuri = 'http://%s:%s' % (self.address, self.port)

    def __repr__(self):
        return '<%s:%s>' % (self.__class__.__name__, self.uri.encode('utf8'))


class MyPlexDevice(object):
    """ This object represents resources connected to your Plex server that provide
        playback ability from your Plex Server, iPhone or Android clients, Plex Web,
        this API, etc. The raw xml for the data presented here can be found at:
        https://plex.tv/devices.xml

        Attributes:
            clientIdentifier (str): Unique ID for this resource.
            connections (list): List of connection URIs for the device.
            device (str): Best guess on the type of device this is (Linux, iPad, AFTB, etc).
            id (str): MyPlex ID of the device.
            model (str): Model of the device (bueller, Linux, x86_64, etc.)
            name (str): Hostname of the device.
            platform (str): OS the resource is running (Linux, Windows, Chrome, etc.)
            platformVersion (str): Version of the platform.
            product (str): Plex product (Plex Media Server, Plex for iOS, Plex Web, etc.)
            productVersion (string): Version of the product.
            provides (str): List of services this resource provides (client, controller,
                sync-target, player, pubsub-player).
            publicAddress (str): Public IP address.
            screenDensity (str): Unknown
            screenResolution (str): Screen resolution (750x1334, 1242x2208, etc.)
            token (str): Plex authentication token for the device.
            vendor (str): Device vendor (ubuntu, etc).
            version (str): Unknown (1, 2, 1.3.3.3148-b38628e, 1.3.15, etc.)
    """
    BASEURL = 'https://plex.tv/devices.xml'

    def __init__(self, data):
        self._data = data
        self.name = data.attrib.get('name')
        self.publicAddress = data.attrib.get('publicAddress')
        self.product = data.attrib.get('product')
        self.productVersion = data.attrib.get('productVersion')
        self.platform = data.attrib.get('platform')
        self.platformVersion = data.attrib.get('platformVersion')
        self.device = data.attrib.get('device')
        self.model = data.attrib.get('model')
        self.vendor = data.attrib.get('vendor')
        self.provides = data.attrib.get('provides')
        self.clientIdentifier = data.attrib.get('clientIdentifier')
        self.version = data.attrib.get('version')
        self.id = data.attrib.get('id')
        self.token = data.attrib.get('token')
        if self.token:
            logfilter.add_secret(self.token)
        self.screenResolution = data.attrib.get('screenResolution')
        self.screenDensity = data.attrib.get('screenDensity')
        self.connections = [connection.attrib.get('uri') for connection in data.iter('Connection')]

    def __repr__(self):
        return '<%s:%s:%s>' % (self.__class__.__name__, self.name.encode('utf8'), self.product.encode('utf8'))

    def connect(self):
        """ Returns a new :class:`~plexapi.client.PlexClient` object. Sometimes there is more than
            one address specified for a server or client. After trying to connect to all
            available addresses for this resource and assuming at least one connection was
            successful, the PlexClient object is built and returned.

            Raises:
                :class:`~plexapi.exceptions.NotFound`: When unable to connect to any addresses for this device.
        """
        # Try connecting to all known resource connections in parellel, but
        # only return the first server (in order) that provides a response.
        listargs = [[c] for c in self.connections]
        results = utils.threaded(self._connect, listargs)
        # At this point we have a list of result tuples containing (url, token, PlexServer)
        # or (url, token, None) in the case a connection could not be
        # established.
        for url, token, result in results:
            okerr = 'OK' if result else 'ERR'
            log.info('Testing device connection: %s?X-Plex-Token=%s %s', url, token, okerr)
        results = [r[2] for r in results if r and r[2] is not None]
        if not results:
            raise NotFound('Unable to connect to resource: %s' % self.name)
        log.info('Connecting to server: %s?X-Plex-Token=%s', results[0].baseurl, results[0].token)
        return results[0]

    def _connect(self, url, results, i):
        try:
            results[i] = (url, self.token, PlexClient(url, self.token))
        except NotFound:
            results[i] = (url, self.token, None)


def _findItem(items, value, attrs=None):
    """ This will return the first item in the list of items where value is
        found in any of the specified attributes.
    """
    attrs = attrs or ['name']
    for item in items:
        for attr in attrs:
            if value.lower() == getattr(item, attr).lower():
                return item
    raise NotFound('Unable to find item %s' % value)


def _listItems(url, token, cls):
    """ Builds list of classes from a XML response. """
    headers = plexapi.BASE_HEADERS
    headers['X-Plex-Token'] = token
    log.info('GET %s?X-Plex-Token=%s', url, token)
    response = requests.get(url, headers=headers, timeout=TIMEOUT)
    data = ElementTree.fromstring(response.text.encode('utf8'))
    return [cls(elem) for elem in data]
