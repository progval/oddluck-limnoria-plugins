###
# Copyright (c) 2024, oddluck
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
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

from supybot import utils, plugins, ircutils, callbacks
from supybot.commands import *
from supybot.i18n import PluginInternationalization
import supybot.log as log
import re
from google import genai
from google.genai import types

_ = PluginInternationalization("Gemini")


class Gemini(callbacks.Plugin):
    """GoogleAI Gemini Chat Plugin"""

    threaded = True

    def __init__(self, irc):
        self.__parent = super(Gemini, self)
        self.__parent.__init__(irc)
        self.history = {}
        self.clients = {}

    def _get_client(self, api_key):
        if api_key not in self.clients:
            self.clients[api_key] = genai.Client(api_key=api_key)
        return self.clients[api_key]

    def chat(self, irc, msg, args, text):
        """Chat Call to the Gemini API"""
        channel = msg.channel
        if not irc.isChannel(channel):
            channel = msg.nick
        if not self.registryValue("enabled", msg.channel):
            return
        api_key = self.registryValue("api_key", msg.channel)
        client = self._get_client(api_key)
        prompt = self.registryValue("prompt", msg.channel).replace("$botnick", irc.nick)
        max_tokens = self.registryValue("max_tokens", msg.channel)
        model_name = self.registryValue("model", msg.channel)
        max_history = self.registryValue("max_history", msg.channel)
        self.history.setdefault(channel, [])
        history = list(self.history[channel][-max_history:]) if max_history >= 1 else []
        config = types.GenerateContentConfig(
            system_instruction=prompt,
            max_output_tokens=max_tokens,
        )
        user_text = "%s: %s" % (msg.nick, text) if self.registryValue("nick_include", msg.channel) else text
        try:
            chat = client.chats.create(model=model_name, config=config, history=history)
            response = chat.send_message(user_text)
        except Exception as e:
            log.error("Gemini failed to fetch response: %s", e)
            return
        if self.registryValue("nick_strip", msg.channel):
            content = re.sub(r"^%s: " % (irc.nick), "", response.text)
        else:
            content = response.text
        prefix = self.registryValue("nick_prefix", msg.channel)
        for line in content.splitlines():
            if line:
                irc.reply(line, prefixNick=prefix)
        if max_history >= 1:
            self.history[channel].append(types.Content(role='user', parts=[types.Part.from_text(text=user_text)]))
            self.history[channel].append(response.candidates[0].content)

    chat = wrap(chat, ["text"])


Class = Gemini


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
