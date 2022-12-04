# coding: utf-8
from __future__ import unicode_literals
from datetime import datetime

import re

from .common import InfoExtractor
from ..compat import (
    compat_str,
    compat_urlparse,
)
from ..utils import (
    ExtractorError,
    int_or_none,
    qualities,
    strip_or_none,
    try_get,
    unified_strdate,
    url_or_none,
)


class ArteTVBaseIE(InfoExtractor):
    _ARTE_LANGUAGES = 'fr|de|en|es|it|pl'
    _API_BASE = 'https://api.arte.tv/api/player/v2'


class ArteTVIE(ArteTVBaseIE):
    _VALID_URL = r'''(?x)
                    https?://
                        (?:
                            (?:www\.)?arte\.tv/(?P<lang>%(langs)s)/videos|
                            api\.arte\.tv/api/player/v\d+/config/(?P<lang_2>%(langs)s)
                        )
                        /(?P<id>\d{6}-\d{3}-[AF])
                    ''' % {'langs': ArteTVBaseIE._ARTE_LANGUAGES}
    _TESTS = [{
        'url': 'https://www.arte.tv/en/videos/088501-000-A/mexico-stealing-petrol-to-survive/',
        'info_dict': {
            'id': '088501-000-A',
            'ext': 'mp4',
            'title': 'Mexico: Stealing Petrol to Survive',
            'upload_date': '20190628',
        },
    }, {
        'url': 'https://www.arte.tv/pl/videos/100103-000-A/usa-dyskryminacja-na-porodowce/',
        'only_matching': True,
    }, {
        'url': 'https://api.arte.tv/api/player/v2/config/de/100605-013-A',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        video_id = mobj.group('id')
        lang = mobj.group('lang') or mobj.group('lang_2')

        info = self._download_json(
            '%s/config/%s/%s' % (self._API_BASE, lang, video_id), video_id)

        attributes = info['data']['attributes']

        upload_date = datetime.fromisoformat(attributes['rights']['begin']).date()

        qfunc = qualities(['MQ', 'HQ', 'EQ', 'SQ'])

        LANGS = {
            'fr': 'F',
            'de': 'A',
            'en': 'E[ANG]',
            'es': 'E[ESP]',
            'it': 'E[ITA]',
            'pl': 'E[POL]',
        }

        langcode = LANGS.get(lang, lang)

        formats = []
        for stream in attributes['streams']:
            format = {
                'format_id': 0,
                #'preference': -10 if f.get('videoFormat') == 'M3U8' else None,
                #'language_preference': lang_pref,
                'format_note': '%s, %s' % (stream['mainQuality']['code'], stream['mainQuality']['label']),
                #'width': int_or_none(f.get('width')),
                #'height': int_or_none(f.get('height')),
                #'tbr': int_or_none(f.get('bitrate')),
                #'quality': qfunc(f.get('quality')),
            }

            #if media_type == 'rtmp':
            #    format['url'] = f['streamer']
            #    format['play_path'] = 'mp4:' + f['url']
            #    format['ext'] = 'flv'
            #else:
            format['url'] = stream['url']

            formats.append(format)

        self._sort_formats(formats)

        return {
            'id': attributes['metadata']['providerId'] or video_id,
            'title': attributes['metadata']['title'],
            'description': attributes['metadata']['description'],
            'upload_date': upload_date,
            'thumbnail': attributes['metadata']['images'][0]['url'],
            'formats': formats,
        }


class ArteTVEmbedIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?arte\.tv/player/v\d+/index\.php\?.*?\bjson_url=.+'
    _TESTS = [{
        'url': 'https://www.arte.tv/player/v5/index.php?json_url=https%3A%2F%2Fapi.arte.tv%2Fapi%2Fplayer%2Fv2%2Fconfig%2Fde%2F100605-013-A&lang=de&autoplay=true&mute=0100605-013-A',
        'info_dict': {
            'id': '100605-013-A',
            'ext': 'mp4',
            'title': 'United we Stream November Lockdown Edition #13',
            'description': 'md5:be40b667f45189632b78c1425c7c2ce1',
            'upload_date': '20201116',
        },
    }, {
        'url': 'https://www.arte.tv/player/v3/index.php?json_url=https://api.arte.tv/api/player/v2/config/de/100605-013-A',
        'only_matching': True,
    }]

    @staticmethod
    def _extract_urls(webpage):
        return [url for _, url in re.findall(
            r'<(?:iframe|script)[^>]+src=(["\'])(?P<url>(?:https?:)?//(?:www\.)?arte\.tv/player/v\d+/index\.php\?.*?\bjson_url=.+?)\1',
            webpage)]

    def _real_extract(self, url):
        qs = compat_urlparse.parse_qs(compat_urlparse.urlparse(url).query)
        json_url = qs['json_url'][0]
        video_id = ArteTVIE._match_id(json_url)
        return self.url_result(
            json_url, ie=ArteTVIE.ie_key(), video_id=video_id)


class ArteTVPlaylistIE(ArteTVBaseIE):
    _VALID_URL = r'https?://(?:www\.)?arte\.tv/(?P<lang>%s)/videos/(?P<id>RC-\d{6})' % ArteTVBaseIE._ARTE_LANGUAGES
    _TESTS = [{
        'url': 'https://www.arte.tv/en/videos/RC-016954/earn-a-living/',
        'info_dict': {
            'id': 'RC-016954',
            'title': 'Earn a Living',
            'description': 'md5:d322c55011514b3a7241f7fb80d494c2',
        },
        'playlist_mincount': 6,
    }, {
        'url': 'https://www.arte.tv/pl/videos/RC-014123/arte-reportage/',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        lang, playlist_id = re.match(self._VALID_URL, url).groups()
        collection = self._download_json(
            '%s/collectionData/%s/%s?source=videos'
            % (self._API_BASE, lang, playlist_id), playlist_id)
        entries = []
        for video in collection['videos']:
            if not isinstance(video, dict):
                continue
            video_url = url_or_none(video.get('url')) or url_or_none(video.get('jsonUrl'))
            if not video_url:
                continue
            video_id = video.get('programId')
            entries.append({
                '_type': 'url_transparent',
                'url': video_url,
                'id': video_id,
                'title': video.get('title'),
                'alt_title': video.get('subtitle'),
                'thumbnail': url_or_none(try_get(video, lambda x: x['mainImage']['url'], compat_str)),
                'duration': int_or_none(video.get('durationSeconds')),
                'view_count': int_or_none(video.get('views')),
                'ie_key': ArteTVIE.ie_key(),
            })
        title = collection.get('title')
        description = collection.get('shortDescription') or collection.get('teaserText')
        return self.playlist_result(entries, playlist_id, title, description)


class ArteTVCategoryIE(ArteTVBaseIE):
    _VALID_URL = r'https?://(?:www\.)?arte\.tv/(?P<lang>%s)/videos/(?P<id>[\w-]+(?:/[\w-]+)*)/?\s*$' % ArteTVBaseIE._ARTE_LANGUAGES
    _TESTS = [{
        'url': 'https://www.arte.tv/en/videos/politics-and-society/',
        'info_dict': {
            'id': 'politics-and-society',
            'title': 'Politics and society',
            'description': 'Investigative documentary series, geopolitical analysis, and international commentary',
        },
        'playlist_mincount': 13,
    },
    ]

    @classmethod
    def suitable(cls, url):
        return (
            not any(ie.suitable(url) for ie in (ArteTVIE, ArteTVPlaylistIE, ))
            and super(ArteTVCategoryIE, cls).suitable(url))

    def _real_extract(self, url):
        lang, playlist_id = re.match(self._VALID_URL, url).groups()
        webpage = self._download_webpage(url, playlist_id)

        items = []
        for video in re.finditer(
                r'<a\b[^>]*?href\s*=\s*(?P<q>"|\'|\b)(?P<url>https?://www\.arte\.tv/%s/videos/[\w/-]+)(?P=q)' % lang,
                webpage):
            video = video.group('url')
            if video == url:
                continue
            if any(ie.suitable(video) for ie in (ArteTVIE, ArteTVPlaylistIE, )):
                items.append(video)

        if items:
            title = (self._og_search_title(webpage, default=None)
                     or self._html_search_regex(r'<title\b[^>]*>([^<]+)</title>', default=None))
            title = strip_or_none(title.rsplit('|', 1)[0]) or self._generic_title(url)

            result = self.playlist_from_matches(items, playlist_id=playlist_id, playlist_title=title)
            if result:
                description = self._og_search_description(webpage, default=None)
                if description:
                    result['description'] = description
                return result
