import re
import urlparse
import requests
import json
from django.core.cache import cache
DETECT_YOUTUBE = re.compile(
    '^(http(s)?://(www\.)?)?youtu(\.?)be(\.com)?.*', re.I
)
DETECT_VIMEO = re.compile('^(http(s)?://(www\.)?)?vimeo\.com.*', re.I)
DETECT_SOUNDCLOUD = re.compile(
    '^(http(s)?://(www\.)?)?soundcloud\.com.*', re.I
)


class UnknownBackendException(Exception):
    pass


class NoIdVideoFound(Exception):
    pass


def detect_backend(url):
    if DETECT_YOUTUBE.match(url):
        return YoutubeBackend(url)
    elif DETECT_VIMEO.match(url):
        return VimeoBackend(url)
    elif DETECT_SOUNDCLOUD.match(url):
        return SoundCloundBackend(url)
    else:
        raise UnknownBackendException


class VideoBackend(object):
    def __init__(self, url):
        self._url = url
        self.code = self.get_code()
        self.url = self.get_url()
        self.thumbnail = self.get_thumbnail_url()
        self.name = self.get_name()

    def get_code(self):
        match = self.re_code.search(self._url)
        if match:
            return match.group('code')
        else:
            parse_data = urlparse.urlparse(self._url)
            try:
                return urlparse.parse_qs(parse_data.query)["v"][0]
            except KeyError:
                pass
            raise NoIdVideoFound

    def get_url(self):
        return self.pattern_url % self.code

    def get_thumbnail_url(self):
        return self.pattern_thumbnail_url % self.code

    def _ombed(self):
        class_name = self.__class__.__name__
        code = self.get_code()
        key = "%s_%s" %( class_name, code )
        json_response = cache.get(key)
        if not json_response:
            d = dict(format="json", url=self._url)
            if 'json' in self._base_url:
                del d['format']
            r = requests.get(self._base_url, params = d)
            self._json_response= json.loads(r.text)
        else:
            self._json_response= json_response

    def get_name(self):
        if not getattr(self,"name",None):
            self._ombed()
            self.name = self._json_response.get("title")
        return self.name
        
class SoundCloundBackend(VideoBackend):
    _base_url = "http://soundcloud.com/oembed"
    url = None

    def __init__(self, url):
        params = {
            'format': 'json', 'url': url,
        }
        r = requests.get(self._base_url, data=params)
        json_response = json.loads(r.text)
        self._response = json_response
        self.name = json_response.get("title")
        self.thumbnail = json_response.get("thumbnail_url")
        match = re.search(r'src="(.*?)"', json_response.get("html"))
        if match:
            self.url = match.groups()[0]
        self.width = json_response.get("width")
        self.height = json_response.get("height")
        super(SoundCloundBackend, self).__init__(url)

    def get_thumbnail_url(self):
        return self.thumbnail

    def get_url(self):
        return self.url

    def get_code(self):
        return self.url
    def get_name(self):
        return self.name


class YoutubeBackend(VideoBackend):
    re_code = re.compile(
        'youtu(?:be\.com/watch\?v=|\.be/)(?P<code>[\w-]*)(&(amp;)?[\w\?=]*)?',
        re.I
    )
    pattern_url = 'http://www.youtube.com/embed/%s?wmode=opaque'
    pattern_thumbnail_url = 'http://img.youtube.com/vi/%s/hqdefault.jpg'
    _base_url = "http://www.youtube.com/oembed"

class VimeoBackend(VideoBackend):
    re_code = re.compile('vimeo\.com/(?P<code>[0-9]+)', re.I)
    pattern_url = 'http://player.vimeo.com/video/%s'
    _base_url = "http://vimeo.com/api/oembed.json"

    def get_thumbnail_url(self):
        self._ombed()
        return self._json_response.get("thumbnail_url")
