###
# Copyright (c) 2019 oddluck
# All rights reserved.
#
#
###

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.ircmsgs as ircmsgs
import requests
import html

try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Weed')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

class Lyrics(callbacks.Plugin):
    """Retrieves song lyrics"""
    threaded = True

    def lyric(self, irc, msg, args, lyric):
        """<artist | song_title>
        Get song lyrics. search must be formatted as artist, song title.
        """
        channel = msg.args[0]
        lyrics = None
        if '|' in lyric:
            query = lyric.split('|')          
        else:
            irc.reply("Searches must be formatted as artist, song title")
            query = None
        if query:
            data = requests.get("https://lyric-api.herokuapp.com/api/find/{0}/{1}".format(query[0].strip(), query[1].strip())).json()
            lyrics = html.unescape(data['lyric']).replace('\n\n', '. ').replace('?\n', '? ').replace('!\n', '! ').replace('.\n', '. ').replace(',\n', ', ').replace('...\n', '... ').replace('\n', ', ')
            if lyrics:
                irc.reply(lyrics)
            else:
                irc.reply("Nothing found.")

    lyric = wrap(lyric, ['text'])

Class = Lyrics
