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
import os
import pexpect
import re

try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('TextAdventures')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

class TextAdventures(callbacks.Plugin):
    """
    Play Text Adventure Games (Infocom, Interactive Fiction, Z-Machine) .
    """
    threaded = True

    def __init__(self, irc):
        self.__parent = super(TextAdventures, self)
        self.__parent.__init__(irc)
        self.game = {}
        self.game_path = "{0}/games/".format(os.path.dirname(os.path.abspath(__file__)))
        self.binary = self.registryValue('dFrotzPath')

    def adventure(self, irc, msg, args, input):
        """<game_name>
        Open <game_name.z*>.
        """
        channel = msg.args[0]
        if not self.registryValue('allowPrivate') and not irc.isChannel(channel):
            irc.reply("Sorry, this game must be played in channel")
            return
        elif self.registryValue('allowPrivate') and not irc.isChannel(channel):
            channel = msg.nick
        game_name = input
        self.game.setdefault(channel, None)
        if self.game[channel]:
            irc.reply("There is a game already in progress on {0}. Please stop that game first.".format(channel))
        else:
            irc.reply("Starting {0} on {1}. Please wait...".format(game_name, channel))
            game_file= "{0}{1}".format(self.game_path, game_name)
            self.game[channel] = pexpect.spawn("{0} -m -S 0 {1}".format(self.binary, game_file))
            response = self.output(self.game[channel])
            for line in response:
                if line.strip() and line.strip() != ".":
                    irc.reply(line, prefixNick=False)
    adventure = wrap(adventure, ['text'])

    def output(self, output):
        response = []
        prompts = ["\n> >", "\n>\r\n>", "\n>", "\n\)", pexpect.TIMEOUT]
        output.expect(prompts, timeout=1)
        response = output.before 
        response = response.decode().splitlines()
        return response

    def doPrivmsg(self, irc, msg):
        channel = msg.args[0]
        if irc.isChannel(channel) and callbacks.addressed(irc.nick, msg):
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        if not self.registryValue('requireCommand') or not irc.isChannel(msg.args[0]):
            self.game.setdefault(channel, None)
            if self.game[channel]:
                command = msg.args[1]
                self.game[channel].sendline(r'{}'.format(command))
                response = self.output(self.game[channel])
                for line in response[1:]:
                    if line.strip() and line.strip() != ".":
                        irc.reply(line, prefixNick=False)
        else:
            return

    def end(self, irc, msg, args):
        """
        End text adventure game.
        """
        channel = msg.args[0]
        if not irc.isChannel(channel):
            channel = msg.nick
        self.game.setdefault(channel, None)
        if self.game[channel]:
            irc.reply("Stopping Game. Thanks for playing.")
        else:
            irc.reply("No game running in {0}".format(channel))
        try:
            self.game[channel].terminate(force=True)
            del self.game[channel]
        except:
            try:
                del self.game[channel]
            except:
                return
            return
    end = wrap(end)

    def z(self, irc, msg, args, command):
        """[<input>]
        Send user input or blank line (ENTER/RETURN) to the game.
        """
        channel = msg.args[0]
        if not irc.isChannel(channel):
            channel = msg.nick
        self.game.setdefault(channel, None)
        if self.game[channel]:
            if command:
                command = re.sub(r'^.?z', r'', r'{}'.format(msg.args[1])).strip()
                self.game[channel].sendline(r'{}'.format(command))
            else:
                self.game[channel].sendline()
            response = self.output(self.game[channel])
            for line in response[1:]:
                if line.strip() and line.strip() != ".":
                    irc.reply(line, prefixNick=False)
        else:
            irc.reply("No game running in {0}?".format(channel))
    z = wrap(z, [optional('text')])

    def games(self, irc, msg, args):
        """
        List files in the game directory.
        """
        reply = ", ".join(sorted(os.listdir(self.game_path)))
        irc.reply(reply, prefixNick=False)
    games = wrap(games)

Class = TextAdventures

