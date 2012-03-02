###
# Copyright (c) 2012, Mike Mueller <mike@subfocal.net>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Do whatever you want
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.schedule as schedule
import supybot.log as log
import supybot.world as world

import random
import re

WHITE = '\x0300'
GREEN = '\x0303'
RED = '\x0305'
YELLOW = '\x0307'
LYELLOW = '\x0308'
LGREEN = '\x0309'
LCYAN = '\x0311'
LBLUE = '\x0312'
LGRAY = '\x0315'

def info(message):
    log.info('Wordgames: ' + message)

def error(message):
    log.error('Wordgames: ' + message)

class Wordgames(callbacks.Plugin):
    "Please see the README file to configure and use this plugin."

    def __init__(self, irc):
        self.__parent = super(Wordgames, self)
        self.__parent.__init__(irc)
        self.games = {}

    def die(self):
        self.__parent.die()

    def doPrivmsg(self, irc, msg):
        channel = msg.args[0]
        game = self.games.get(channel)
        if game:
            game.handle_message(msg)

    def wordshrink(self, irc, msgs, args, channel, length):
        """[length] (default: 4)

        Start a word-shrink game. Make new words by dropping one letter from
        the previous word.
        """
        if length < 4 or length > 7:
            irc.reply('Please use a length between 4 and 7.')
        else:
            self._start_game(WordShrink, irc, channel, length)
    wordshrink = wrap(wordshrink, ['channel', optional('int', 4)])

    def wordtwist(self, irc, msgs, args, channel, length):
        """[length] (default: 4)

        Start a word-twist game. Make new words by changing one letter in
        the previous word.
        """
        if length < 4 or length > 7:
            irc.reply('Please use a length between 4 and 7.')
        else:
            self._start_game(WordTwist, irc, channel, length)
    wordtwist = wrap(wordtwist, ['channel', optional('int', 4)])

    def wordquit(self, irc, msgs, args, channel):
        """(takes no arguments)

        Stop any currently running word game.
        """
        game = self.games.get(channel)
        if game and game.is_running():
            game.stop()
        else:
            irc.reply('No word game currently running.')
    wordquit = wrap(wordquit, ['channel'])

    def _get_words(self):
        return map(str.strip, file(self.registryValue('wordFile')).readlines())

    def _start_game(self, Game, irc, channel, length):
        game = self.games.get(channel)
        if game and game.is_running():
            irc.reply('A word game is already running here.')
            game.show()
        else:
            self.games[channel] = Game(self._get_words(), irc, channel, length)
            self.games[channel].start()

class BaseGame(object):
    "Base class for the games in this plugin."

    def __init__(self, words, irc, channel):
        self.words = words
        self.irc = irc
        self.channel = channel
        self.running = False

    def gameover(self):
        "The game is finished."
        self.running = False

    def start(self):
        "Start the current game."
        self.running = True

    def stop(self):
        "Shut down the current game."
        self.running = False

    def show(self):
        "Show the current state of the game."
        pass

    def is_running(self):
        return self.running

    def announce(self, msg):
        "Announce a message with the game title prefix."
        text = '%s%s%s:%s %s' % (
            LBLUE, self.__class__.__name__, WHITE, LGRAY, msg)
        self.send(text)

    def send(self, msg):
        "Relay a message to the channel."
        self.irc.queueMsg(ircmsgs.privmsg(self.channel, msg))

    def handle_message(self, msg):
        "Handle incoming messages on the channel."
        pass

    def _join_words(self, words):
        sep = "%s > %s" % (LGREEN, YELLOW)
        text = words[0] + sep
        text += sep.join(words[1:-1])
        text += sep + LGRAY + words[-1]
        return text

class WordChain(BaseGame):
    "Base class for word-chain games like WordShrink and WordTwist."
    def __init__(self, words, irc, channel, length):
        super(WordChain, self).__init__(words, irc, channel)
        self.solution_length = length
        self.solution = []
        self.solutions = []
        self.word_map = {}

    def start(self):
        super(WordChain, self).start()
        self.build_word_map()
        words = filter(lambda s: len(s) >= 2+self.solution_length, self.words)
        while not self.solution:
            while len(self.solution) < self.solution_length:
                self.solution = [random.choice(words)]
                for i in range(1, self.solution_length):
                    values = self.word_map[self.solution[-1]]
                    if not values: break
                    self.solution.append(random.choice(values))
            self.solutions = []
            self._find_solutions()
            # Ensure no solution is trivial
            for solution in self.solutions:
                if self.is_trivial_solution(solution):
                    self.solution = []
                    break
        self.show()

    def show(self):
        words = [self.solution[0]]
        for word in self.solution[1:-1]:
            words.append("-" * len(word))
        words.append(self.solution[-1])
        self.announce(self._join_words(words))
        num = len(self.solutions)
        self.send("(%s%d%s possible solution%s)" %
                  (WHITE, num, LGRAY, '' if num == 1 else 's'))

    def stop(self):
        super(WordChain, self).stop()
        self.announce(self._join_words(self.solution))

    def handle_message(self, msg):
        words = map(str.strip, msg.args[1].split('>'))
        for word in words:
            if not re.match(r"^[a-z]+$", word):
                return
        if len(words) == len(self.solution) - 2:
            words = [self.solution[0]] + words + [self.solution[-1]]
        if self._valid_solution(msg.nick, words):
            if self.running:
                self.announce("%s%s%s got it!" % (WHITE, msg.nick, LGRAY))
                self.announce(self._join_words(words))
                self.gameover()
            else:
                self.send("%s: Your solution is also valid." % msg.nick)

    # Override in game class
    def build_word_map(self):
        "Build a map of word -> [word1, word2] for all valid transitions."
        pass

    # Override in game class
    def is_trivial_solution(self, solution):
        return False

    def get_successors(self, word):
        "Lookup a word in the map and return list of possible successor words."
        return self.word_map.get(word, [])

    def _find_solutions(self, seed=None):
        "Recursively find and save all solutions for the puzzle."
        if seed is None:
            seed = [self.solution[0]]
            self.solutions = []
            self._find_solutions(seed)
        elif len(seed) == len(self.solution) - 1:
            if self.solution[-1] in self.get_successors(seed[-1]):
                self.solutions.append(seed + [self.solution[-1]])
        else:
            words = self.get_successors(seed[-1])
            for word in words:
                if word == self.solution[-1]:
                    self.solutions.append(seed + [word])
                else:
                    self._find_solutions(seed + [word])

    def _valid_solution(self, nick, words):
        # Ignore things that don't look like attempts to answer
        if len(words) != len(self.solution):
            return False
        # Check for incorrect start/end words
        if len(words) == len(self.solution):
            if words[0] != self.solution[0]:
                self.send('%s: %s is not the starting word.' % (nick, words[0]))
                return False
            if words[-1] != self.solution[-1]:
                self.send('%s: %s is not the final word.' % (nick, words[-1]))
                return False
        # Add the start/end words (if not present) to simplify the test logic
        if len(words) == len(self.solution) - 2:
            words = [self.solution[0]] + words + [self.solution[-1]]
        for word in words:
            if word not in self.words:
                self.send("%s: %s is not a word I know." % (nick, word))
                return False
        for i in range(0, len(words)-1):
            if words[i+1] not in self.get_successors(words[i]):
                self.send("%s: %s does not follow from %s." %
                        (nick, words[i+1], words[i]))
                return False
        return True

class WordShrink(WordChain):
    def __init__(self, words, irc, channel, length):
        super(WordShrink, self).__init__(words, irc, channel, length)

    def build_word_map(self):
        "Build a map of word -> [word1, word2] for all valid transitions."
        keymap = {}
        for word in self.words:
            s = "".join(sorted(word))
            if s in keymap:
                keymap[s].append(word)
            else:
                keymap[s] = [word]
        self.word_map = {}
        for word1 in self.words:
            s = "".join(sorted(word1))
            if s in self.word_map:
                self.word_map[word1] = self.word_map[s]
            else:
                self.word_map[s] = self.word_map[word1] = []
                for i in range(0, len(s)):
                    t = s[0:i] + s[i+1:]
                    for word2 in keymap.get(t, []):
                        self.word_map[s].append(word2)

    def is_trivial_solution(self, solution):
        "Consider pure substring solutions trivial."
        for i in range(0, len(solution)-1):
            for j in range(i+1, len(solution)):
                if solution[i].find(solution[j]) >= 0:
                    return True
        return False

class WordTwist(WordChain):
    def __init__(self, words, irc, channel, length):
        super(WordTwist, self).__init__(words, irc, channel, length)

    def build_word_map(self):
        "Build the map of word -> [word1, word2, ...] for all valid pairs."
        keymap = {}
        wildcard = '*'
        for word in self.words:
            for pos in range(0, len(word)):
                key = word[0:pos] + wildcard + word[pos+1:]
                if key not in keymap:
                    keymap[key] = [word]
                else:
                    keymap[key].append(word)
        self.word_map = {}
        for word in self.words:
            self.word_map[word] = []
            for pos in range(0, len(word)):
                key = word[0:pos] + wildcard + word[pos+1:]
                self.word_map[word] += filter(
                    lambda w: w != word, keymap.get(key, []))

    def is_trivial_solution(self, solution):
        "If it's possible to get there in fewer hops, this is trivial."
        return len(solution) < self.solution_length

Class = Wordgames

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
