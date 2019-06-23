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
    _ = PluginInternationalization('Infocom')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

class Frotz(callbacks.Plugin):
    """
    Play Infocom (Interactive Fiction, Z_machine) Games.
    """
    threaded = True

    def __init__(self, irc):
        self.__parent = super(Frotz, self)
        self.__parent.__init__(irc)
        self.game = {}
        self.game_path = "{0}/games/".format(os.path.dirname(os.path.abspath(__file__)))
        self.binary = self.registryValue('dfrotzPath')

    def load(self, irc, msg, args, input):
        """<game_name>
        Load <game_name.z*>.
        """
        channel = msg.args[0]
        if not irc.isChannel(channel):
            channel = msg.nick
        game_name = input
        self.game.setdefault(channel, None)
        if self.game[channel]:
            irc.reply("There is a game already in progress on {0}. Please stop that game first.".format(channel))
        else:
            irc.reply("Starting {0} on {1}. Please wait...".format(game_name, channel))
            game_file= "{0}{1}".format(self.game_path, game_name)
            self.game[channel] = pexpect.spawn("{0} -S 0 {1}".format(self.binary, game_file))
            response = self.output(self.game[channel])
            for line in response:
                if line.strip() and line.strip() != ".":
                    irc.reply(line, prefixNick=False)
    load = wrap(load, ['text'])

    def output(self, output):
        response = []
        prompts = ["> >$", ">$", "\*\*\*MORE\*\*\*", "\) \[Hit any key to continue.\]", "\[Press RETURN or ENTER to begin.\]", "\[Hit any key to continue.\]", pexpect.TIMEOUT]
        output.expect(prompts, timeout=2)
        response = output.before
        try:
            while not output.match.group().decode().endswith(">"):
                output.sendline()
                output.expect(prompts, timeout=2)
                response += output.before
        except:
            pass
        response = response.decode().splitlines()
        return response

    def doPrivmsg(self, irc, msg):
        channel = msg.args[0]
        if callbacks.addressed(irc.nick, msg):
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        self.game.setdefault(channel, None)
        if self.game[channel]:
            command = msg.args[1]
            self.game[channel].sendline(command)
            response = self.output(self.game[channel])
            for line in response[1:]:
                if line.strip() and line.strip() != ".":
                    irc.reply(line, prefixNick=False)

    def stop(self, irc, msg, args):
        """
        Stop game.
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
    stop = wrap(stop)

    def z(self, irc, msg, args, input):
        """[<input>]
        Send user input or blank line (ENTER/RETURN) to the game.
        """
        channel = msg.args[0]
        if not irc.isChannel(channel):
            channel = msg.nick
        self.game.setdefault(channel, None)
        if input:
            command = input.strip()
        else:
            command = None
        if self.game[channel]:
            if command:
                self.game[channel].sendline(command)
            else:
                self.game[channel].sendline()
            response = self.output(self.game[channel])
            for line in response[1:]:
                if line.strip() and line.strip() != ".":
                    irc.reply(line, prefixNick=False)
        else:
            irc.reply("No game running in {0}?".format(channel))
    z = wrap(z, [additional('text')])

    def games(self, irc, msg, args):
        """
        List files in the game directory.
        """
        reply = ", ".join(sorted(os.listdir(self.game_path)))
        irc.reply(reply, prefixNick=False)
    games = wrap(games)

Class = Frotz

