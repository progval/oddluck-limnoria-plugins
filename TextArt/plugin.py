###
# Copyright (c) 2020, oddluck <oddluck@riseup.net>
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

import supybot.ansi as ansi
import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.ircdb as ircdb
import supybot.callbacks as callbacks
import supybot.ircmsgs as ircmsgs
import supybot.log as log
import os
import requests
from PIL import Image, ImageOps, ImageFont, ImageDraw, ImageEnhance
import numpy as np
import sys, math
import re
import asyncio
import pexpect
import time
import random
import pyimgur
import json
from .colors import (
    rgbColors,
    colors16,
    colors83,
    colors99,
    ansi16,
    ansi83,
    ansi99,
    x16colors,
)

try:
    from bs4 import BeautifulSoup
except ImportError as e:
    raise ImportError("%s. Try installing beautifulsoup4." % (e.args[0])) from None

try:
    from supybot.i18n import PluginInternationalization

    _ = PluginInternationalization("TextArt")
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x


class TextArt(callbacks.Plugin):
    """TextArt: Make Text Art"""

    threaded = True

    def __init__(self, irc):
        self.__parent = super(TextArt, self)
        self.__parent.__init__(irc)
        self.colors = 99
        self.stopped = {}
        self.old_color = None
        self.source_colors = 0
        self.agents = self.registryValue("userAgents")
        self.matches = {}

    def doPrivmsg(self, irc, msg):
        channel = msg.args[0]
        if not irc.isChannel(channel):
            channel = msg.nick
        self.stopped.setdefault(channel, None)
        if msg.args[1].lower().strip()[1:] == "cq":
            self.stopped[channel] = True

    def doPaste(self, description, paste):
        try:
            description = description.split("/")[-1]
            apikey = self.registryValue("pasteAPI")
            payload = {"description": description, "sections": [{"contents": paste}]}
            headers = {"X-Auth-Token": apikey}
            post_response = requests.post(
                url="https://api.paste.ee/v1/pastes", json=payload, headers=headers
            )
            response = json.loads(post_response.content)
            return response["link"].replace("/p/", "/r/")
        except:
            return (
                "Error. Did you set a valid Paste.ee API Key?"
                " https://paste.ee/account/api"
            )

    def renderImage(self, text, size=18, defaultBg=1, defaultFg=0):
        try:
            if utf8 and not isinstance(text, unicode):
                text = text.decode("utf-8")
        except:
            pass
        text = text.replace("\t", " ")
        self.strip_colors_regex = re.compile(
            "(\x03([0-9]{1,2})(,[0-9]{1,2})?)|[\x0f\x02\x1f\x03\x16]"
        ).sub
        path = os.path.dirname(os.path.abspath(__file__))
        defaultFont = "{0}/DejaVu.ttf".format(path)

        def strip_colors(string):
            return self.strip_colors_regex("", string)

        _colorRegex = re.compile("(([0-9]{1,2})(,([0-9]{1,2}))?)")
        IGNORE_CHRS = ("\x16", "\x1f", "\x02", "\x03", "\x0f")
        lineLens = [len(line) for line in strip_colors(text).splitlines()]
        maxWidth, height = max(lineLens), len(lineLens)
        font = ImageFont.truetype(defaultFont, size)
        fontX = 10
        fontY = 20
        imageX, imageY = maxWidth * fontX, height * fontY
        image = Image.new("RGB", (imageX, imageY), rgbColors[defaultBg])
        draw = ImageDraw.Draw(image)
        dtext, drect, match, x, y, fg, bg = (
            draw.text,
            draw.rectangle,
            _colorRegex.match,
            0,
            0,
            defaultFg,
            defaultBg,
        )
        for text in text.split("\n"):
            ll, i = len(text), 0
            while i < ll:
                chr = text[i]
                if chr == "\x03":
                    m = match(text[i + 1 : i + 6])
                    if m:
                        i += len(m.group(1))
                        fg = int(m.group(2))
                        if m.group(4) is not None:
                            bg = int(m.group(4))
                    else:
                        bg, fg = defaultBg, defaultFg
                elif chr == "\x0f":
                    fg, bg = defaultFg, defaultBg
                elif chr not in IGNORE_CHRS:
                    if bg != defaultBg:  # bg is not white, render it
                        drect((x, y, x + fontX, y + fontY), fill=rgbColors[bg])
                    if bg != fg:  # text will show, render it. this saves a lot of time!
                        dtext((x, y), chr, font=font, fill=rgbColors[fg])
                    x += fontX
                i += 1
            y += fontY
            fg, bg, x = defaultFg, defaultBg, 0
        return image

    def getColor(self, pixel, speed):
        pixel = tuple(pixel)
        try:
            return self.matches[pixel]
        except KeyError:
            if self.colors == 16:
                colors = list(colors16.keys())
            elif self.colors == 99:
                colors = list(colors99.keys())
            else:
                colors = list(colors83.keys())
            closest_colors = sorted(
                colors,
                key=lambda color: self.distance(color, self.rgb2lab(pixel), speed),
            )
            closest_color = closest_colors[0]
            if self.colors == 16:
                self.matches[pixel] = colors16[closest_color]
            elif self.colors == 99:
                self.matches[pixel] = colors99[closest_color]
            else:
                self.matches[pixel] = colors83[closest_color]
            self.source_colors += 1
            return self.matches[pixel]

    def rgb2lab(self, inputColor):
        try:
            return self.labmatches[inputColor]
        except:
            num = 0
            RGB = [0, 0, 0]
            for value in inputColor:
                value = float(value) / 255
                if value > 0.04045:
                    value = ((value + 0.055) / 1.055) ** 2.4
                else:
                    value = value / 12.92
                RGB[num] = value * 100
                num = num + 1
            XYZ = [
                0,
                0,
                0,
            ]
            X = RGB[0] * 0.4124 + RGB[1] * 0.3576 + RGB[2] * 0.1805
            Y = RGB[0] * 0.2126 + RGB[1] * 0.7152 + RGB[2] * 0.0722
            Z = RGB[0] * 0.0193 + RGB[1] * 0.1192 + RGB[2] * 0.9505
            XYZ[0] = round(X, 4)
            XYZ[1] = round(Y, 4)
            XYZ[2] = round(Z, 4)
            XYZ[0] = (
                float(XYZ[0]) / 95.047
            )  # ref_X =  95.047   Observer= 2°, Illuminant= D65
            XYZ[1] = float(XYZ[1]) / 100.0  # ref_Y = 100.000
            XYZ[2] = float(XYZ[2]) / 108.883  # ref_Z = 108.883
            num = 0
            for value in XYZ:
                if value > 0.008856:
                    value = value ** (0.3333333333333333)
                else:
                    value = (7.787 * value) + (16 / 116)
                XYZ[num] = value
                num = num + 1
            Lab = [0, 0, 0]
            L = (116 * XYZ[1]) - 16
            a = 500 * (XYZ[0] - XYZ[1])
            b = 200 * (XYZ[1] - XYZ[2])
            Lab[0] = round(L, 4)
            Lab[1] = round(a, 4)
            Lab[2] = round(b, 4)
            self.labmatches[inputColor] = Lab
            return self.labmatches[inputColor]

    def ciede2000(self, lab1, lab2):
        """ CIEDE2000 color difference formula. https://peteroupc.github.io/colorgen.html"""
        dl = lab2[0] - lab1[0]
        hl = lab1[0] + dl * 0.5
        sqb1 = lab1[2] * lab1[2]
        sqb2 = lab2[2] * lab2[2]
        c1 = math.sqrt(lab1[1] * lab1[1] + sqb1)
        c2 = math.sqrt(lab2[1] * lab2[1] + sqb2)
        hc7 = math.pow((c1 + c2) * 0.5, 7)
        trc = math.sqrt(hc7 / (hc7 + 6103515625))
        t2 = 1.5 - trc * 0.5
        ap1 = lab1[1] * t2
        ap2 = lab2[1] * t2
        c1 = math.sqrt(ap1 * ap1 + sqb1)
        c2 = math.sqrt(ap2 * ap2 + sqb2)
        dc = c2 - c1
        hc = c1 + dc * 0.5
        hc7 = math.pow(hc, 7)
        trc = math.sqrt(hc7 / (hc7 + 6103515625))
        h1 = math.atan2(lab1[2], ap1)
        if h1 < 0:
            h1 = h1 + math.pi * 2
        h2 = math.atan2(lab2[2], ap2)
        if h2 < 0:
            h2 = h2 + math.pi * 2
        hdiff = h2 - h1
        hh = h1 + h2
        if abs(hdiff) > math.pi:
            hh = hh + math.pi * 2
            if h2 <= h1:
                hdiff = hdiff + math.pi * 2
            else:
                hdiff = hdiff - math.pi * 2
        hh = hh * 0.5
        t2 = 1 - 0.17 * math.cos(hh - math.pi / 6) + 0.24 * math.cos(hh * 2)
        t2 = t2 + 0.32 * math.cos(hh * 3 + math.pi / 30)
        t2 = t2 - 0.2 * math.cos(hh * 4 - math.pi * 63 / 180)
        dh = 2 * math.sqrt(c1 * c2) * math.sin(hdiff * 0.5)
        sqhl = (hl - 50) * (hl - 50)
        fl = dl / (1 + (0.015 * sqhl / math.sqrt(20 + sqhl)))
        fc = dc / (hc * 0.045 + 1)
        fh = dh / (t2 * hc * 0.015 + 1)
        dt = 30 * math.exp(
            -math.pow(36 * hh - 55 * math.pi, 2) / (25 * math.pi * math.pi)
        )
        r = -2 * trc * math.sin(2 * dt * math.pi / 180)
        de =  math.sqrt(fl * fl + fc * fc + fh * fh + r * fc * fh)
        dep = 1.43 * de ** 0.70
        return dep

    def distance(self, c1, c2, speed):
        if speed == "fast":
            delta_e = math.sqrt(
                (c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2
            )
        elif speed == "slow":
            delta_e = self.ciede2000(c1, c2)
        return delta_e

    def process_ansi(self, ansi):
        if self.colors == 16:
            colors = ansi16
        elif self.colors == 99:
            colors = ansi99
        else:
            colors = ansi83
        x16color1 = None
        x16color2 = None
        x256color1 = None
        x256color2 = None
        effect = None
        ansi = ansi.lower().strip("\x1b[").strip("m").split(";")
        if len(ansi) > 1:
            i = 0
            while i < len(ansi):
                if i >= len(ansi):
                    break
                elif ansi[i] == "0":
                    effect = 0
                    i += 1
                    continue
                elif ansi[i] == "1":
                    effect = 1
                    i += 1
                    continue
                elif ansi[i] == "4":
                    effect = 4
                    i += 1
                    continue
                elif ansi[i] == "2":
                    effect = 2
                    i += 1
                    continue
                elif int(ansi[i]) > 29 and int(ansi[i]) < 38:
                    if effect == 1 or ansi[-1] == "1":
                        x16color1 = x16colors["{0};1".format(ansi[i])]
                        effect = None
                        i += 1
                        continue
                    else:
                        x16color1 = x16colors[ansi[i]]
                        i += 1
                        continue
                elif int(ansi[i]) > 39 and int(ansi[i]) < 48:
                    if effect == 1 or ansi[-1] == "1":
                        x16color2 = x16colors["{0};1".format(ansi[i])]
                        effect = None
                        i += 1
                        continue
                    else:
                        x16color2 = x16colors[ansi[i]]
                        i += 1
                        continue
                elif ansi[i] == "38":
                    x256color1 = colors[int(ansi[i + 2])]
                    i += 3
                    continue
                elif ansi[i] == "48":
                    x256color2 = colors[int(ansi[i + 2])]
                    i += 3
                    continue
                else:
                    i += 1
                    continue
            if x16color1 and x16color2:
                color = "\x03{0},{1}".format(x16color1, x16color2)
            elif x256color1 and x256color2:
                color = "\x03{0},{1}".format(x256color1, x256color2)
            elif x16color1:
                color = "\x03{0}".format(x16color1)
            elif x16color2:
                color = "\x0399,{0}".format(x16color2)
            elif x256color1:
                color = "\x03{0}".format(x256color1)
            elif x256color2:
                color = "\x0399,{0}".format(x256color2)
            else:
                color = ""
            if effect == 1:
                color += "\x02"
            if effect == 4:
                color += "\x1F"
        elif len(ansi[0]) > 0:
            if ansi[0] == "0":
                color = "\x0F"
            elif ansi[0] == "1" or ansi[0] == "2":
                color = "\x02"
            elif ansi[0] == "4":
                color = "\x1F"
            elif int(ansi[0]) > 29 and int(ansi[0]) < 38:
                color = "\x03{0}".format(x16colors[ansi[0]])
            elif int(ansi[0]) > 39 and int(ansi[0]) < 48:
                color = "\x0399,{0}".format(x16colors[ansi[0]])
            elif ansi[0][-1] == "c":
                color = " " * int(ansi[0][:-1])
            else:
                color = ""
        else:
            color = ""
        if color != self.old_color:
            self.old_color = color
            return color
        else:
            return ""

    def ansi2irc(self, output):
        output = output.replace("\x1b(B\x1b[m", "\x1b[0m")
        output = output.replace("\x1b\x1b", "\x1b")
        output = re.sub(
            "\x1B\[[0-?]*[ -/]*[@-~]", lambda m: self.process_ansi(m.group(0)), output
        )
        output = re.sub("\x0399,(\d\d)\x03(\d\d)", "\x03\g<2>,\g<1>", output)
        output = output.replace("\x0F\x03", "\x03")
        return output

    def png(self, irc, msg, args, optlist, url):
        """[--bg] [--fg] <url>
        Generate PNG from text file
        """
        optlist = dict(optlist)
        if "bg" in optlist:
            bg = optlist.get("bg")
        else:
            bg = 1
        if "fg" in optlist:
            fg = optlist.get("fg")
        else:
            fg = 0
        if url.startswith("https://paste.ee/p/"):
            url = re.sub("https://paste.ee/p/", "https://paste.ee/r/", url)
        ua = random.choice(self.agents)
        header = {"User-Agent": ua}
        try:
            r = requests.get(url, stream=True, headers=header, timeout=10)
            r.raise_for_status()
        except (
            requests.exceptions.RequestException,
            requests.exceptions.HTTPError,
        ) as e:
            log.debug("TextArt: error retrieving data for png: {0}".format(e))
            return
        if "text/plain" in r.headers["content-type"] or url.startswith(
            "https://paste.ee/r/"
        ):
            try:
                file = r.content.decode()
            except:
                file = r.content.decode("cp437")
        else:
            irc.reply("Invalid file type.", private=False, notice=False)
            return
        file = re.sub("(\x03(\d+).*)\x03,", "\g<1>\x03\g<2>,", file).replace(
            "\r\n", "\n"
        )
        im = self.renderImage(file, 18, bg, fg)
        path = os.path.dirname(os.path.abspath(__file__))
        filepath = "{0}/tmp/tldr.png".format(path)
        im.save(filepath, "PNG")
        CLIENT_ID = self.registryValue("imgurAPI")
        imgur = pyimgur.Imgur(CLIENT_ID)
        uploaded_image = imgur.upload_image(filepath, title=url)
        irc.reply(uploaded_image.link, noLengthCheck=True, private=False, notice=False)

    png = wrap(png, [getopts({"bg": "int", "fg": "int"}), "text"])

    async def reply(self, irc, output, channel, delay):
        self.stopped.setdefault(channel, None)
        for line in output:
            if self.stopped[channel]:
                return
            if not line.strip():
                line = "\xa0"
            irc.sendMsg(ircmsgs.privmsg(channel, line))
            await asyncio.sleep(delay)

    def artii(self, irc, msg, args, channel, optlist, text):
        """[<channel>] [--font <font>] [--color <color1,color2>] [<text>]
        Text to ASCII figlet fonts using the artii API
        """
        if not channel:
            channel = msg.args[0]
        if channel != msg.args[0] and not ircdb.checkCapability(msg.prefix, "admin"):
            irc.errorNoCapability("admin")
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        if len(text) > self.registryValue("maxLength", msg.channel):
            return
        if len(text.split(" ")) > self.registryValue("maxWords", msg.channel):
            return
        elif len(text.split("|")) > self.registryValue("maxWords", msg.channel):
            return
        optlist = dict(optlist)
        font = None
        words = []
        if "delay" in optlist and ircdb.checkCapability(msg.prefix, "admin"):
            delay = optlist.get("delay")
        else:
            delay = self.registryValue("delay", msg.args[0])
        if text:
            text = text.strip()
            if "|" in text:
                words = text.split("|")
        if "color" in optlist:
            color = optlist.get("color")
            if "," in color:
                color = color.split(",")
                color1 = color[0].strip()
                color2 = color[1].strip()
            else:
                color1 = color
                color2 = None
        else:
            color1 = None
            color2 = None
        if "font" in optlist:
            font = optlist.get("font")
            if words:
                for word in words:
                    if word.strip():
                        try:
                            data = requests.get(
                                "https://artii.herokuapp.com/make?text={0}&font={1}"
                                .format(word.strip(), font),
                                timeout=10,
                            )
                            data.raise_for_status()
                        except (
                            requests.exceptions.RequestException,
                            requests.exceptions.HTTPError,
                        ) as e:
                            log.debug(
                                "TextArt: error retrieving data for artii: {0}".format(
                                    e
                                )
                            )
                            return
                        output = []
                        for line in data.content.decode().splitlines():
                            line = ircutils.mircColor(line, color1, color2)
                            output.append(line)
                        asyncio.run(self.reply(irc, output, channel, delay))
            else:
                try:
                    data = requests.get(
                        "https://artii.herokuapp.com/make?text={0}&font={1}".format(
                            text, font
                        ),
                        timeout=10,
                    )
                    data.raise_for_status()
                except (
                    requests.exceptions.RequestException,
                    requests.exceptions.HTTPError,
                ) as e:
                    log.debug("TextArt: error retrieving data for artii: {0}".format(e))
                    return
                output = []
                for line in data.content.decode().splitlines():
                    line = ircutils.mircColor(line, color1, color2)
                    output.append(line)
                asyncio.run(self.reply(irc, output, channel, delay))
        elif "font" not in optlist:
            if words:
                for word in words:
                    if word.strip():
                        try:
                            data = requests.get(
                                "https://artii.herokuapp.com/make?text={0}&font=univers"
                                .format(word.strip()),
                                timeout=10,
                            )
                            data.raise_for_status()
                        except (
                            requests.exceptions.RequestException,
                            requests.exceptions.HTTPError,
                        ) as e:
                            log.debug(
                                "TextArt: error retrieving data for artii: {0}".format(
                                    e
                                )
                            )
                            return
                        output = []
                        for line in data.content.decode().splitlines():
                            line = ircutils.mircColor(line, color1, color2)
                            output.append(line)
                        asyncio.run(self.reply(irc, output, channel, delay))
            else:
                try:
                    data = requests.get(
                        "https://artii.herokuapp.com/make?text={0}&font=univers".format(
                            text
                        ),
                        timeout=10,
                    )
                    data.raise_for_status()
                except (
                    requests.exceptions.RequestException,
                    requests.exceptions.HTTPError,
                ) as e:
                    log.debug("TextArt: error retrieving data for artii: {0}".format(e))
                    return
                output = []
                for line in data.content.decode().splitlines():
                    line = ircutils.mircColor(line, color1, color2)
                    output.append(line)
                asyncio.run(self.reply(irc, output, channel, delay))

    artii = wrap(
        artii,
        [
            optional("channel"),
            getopts({"font": "text", "color": "text", "delay": "float"}),
            "text",
        ],
    )

    def fontlist(self, irc, msg, args):
        """
        Get list of artii figlet fonts.
        """
        try:
            fontlist = requests.get(
                "https://artii.herokuapp.com/fonts_list", timeout=10
            )
            fontlist.raise_for_status()
        except (
            requests.exceptions.RequestException,
            requests.exceptions.HTTPError,
        ) as e:
            log.debug("textArt: error retrieving data for fontlist: {0}".format(e))
            return
        response = sorted(fontlist.content.decode().split("\n"))
        irc.reply(str(response).replace("'", "").replace("[", "").replace("]", ""))

    fontlist = wrap(fontlist)

    def img(self, irc, msg, args, channel, optlist, url):
        """[<#channel>] [--delay #.#] [--w <###>] [--s <#.#] [--16] [--99] [--83] [--ascii] [--block] [--1/2] [--chars <text>] [--ramp <text>] [--bg <0-98>] [--fg <0-98>] [--no-color] [--invert] <url>
        Image to IRC art.
        --w columns.
        --s saturation (1.0).
        --16 colors 0-15.
        --99 colors 0-98.
        --83 colors 16-98.
        --ascii color ascii.
        --block space block.
        --1/2 for 1/2 block
        --chars <TEXT> color text.
        --ramp <TEXT> set ramp (".:-=+*#%@").
        --bg <0-98> set bg.
        --fg <0-99> set fg.
        --no-color greyscale ascii.
        --invert inverts ramp.
        """
        if not channel:
            channel = msg.args[0]
        if channel != msg.args[0] and not ircdb.checkCapability(msg.prefix, "admin"):
            irc.errorNoCapability("admin")
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        optlist = dict(optlist)
        gscale = "\xa0"
        if "16" in optlist:
            self.colors = 16
        elif "83" in optlist:
            self.colors = 83
        elif "99" in optlist:
            self.colors = 99
        else:
            self.colors = self.registryValue("colors", msg.args[0])
        if "fast" in optlist:
            speed = "fast"
        elif "slow" in optlist:
            speed = "slow"
        else:
            speed = self.registryValue("speed", msg.args[0]).lower()
        if "delay" in optlist and ircdb.checkCapability(msg.prefix, "admin"):
            delay = optlist.get("delay")
        else:
            delay = self.registryValue("delay", msg.args[0])
        if "quantize" in optlist:
            quantize = True
        elif "no-quantize" in optlist:
            quantize = False
        else:
            quantize = self.registryValue("quantize", msg.args[0])
        if "bg" in optlist:
            bg = optlist.get("bg")
        else:
            bg = self.registryValue("bg", msg.args[0])
        if "fg" in optlist:
            fg = optlist.get("fg")
        else:
            fg = self.registryValue("fg", msg.args[0])
        if "chars" in optlist:
            type = "ascii"
            gscale = optlist.get("chars")
        elif "ramp" in optlist:
            type = "ascii"
            gscale = optlist.get("ramp")
        elif "ascii" in optlist and bg == 0 or bg == 98:
            type = "ascii"
            gscale = (
                "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:\"^`'."
            )
        elif "ascii" in optlist:
            type = "ascii"
            gscale = (
                ".'`^\":;Il!i><~+_-?][}{1)(|\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
            )
        elif "1/2" in optlist:
            type = "1/2"
        elif "block" in optlist:
            type = "ascii"
            gscale = "\xa0"
        else:
            type = self.registryValue("imgDefault", msg.args[0]).lower()
        if "no-color" in optlist and "ramp" not in optlist and bg == 0 or bg == 98:
            type = "no-color"
            gscale = "@%#*+=-:. "
        elif "no-color" in optlist and "ramp" not in optlist:
            type = "no-color"
            gscale = " .:-=+*#%@"
        elif "no-color" in optlist and "chars" not in optlist:
            type = "no-color"
        if not gscale.strip():
            gscale = "\xa0"
        if "invert" in optlist and "chars" not in optlist and gscale != "\xa0":
            gscale = gscale[::-1]
        if "w" in optlist:
            cols = optlist.get("w")
        elif type == "ascii" or type == "no-color" or type == "block":
            cols = self.registryValue("asciiWidth", msg.args[0])
        else:
            cols = self.registryValue("blockWidth", msg.args[0])
        if "s" in optlist:
            s = float(optlist.get("s"))
        ua = random.choice(self.agents)
        header = {"User-Agent": ua}
        image_formats = ("image/png", "image/jpeg", "image/jpg", "image/gif")
        try:
            r = requests.get(url, stream=True, headers=header, timeout=10)
            r.raise_for_status()
        except (
            requests.exceptions.RequestException,
            requests.exceptions.HTTPError,
        ) as e:
            log.debug("TextArt: error retrieving data for img: {0}".format(e))
            return
        if r.headers["content-type"] in image_formats and r.status_code == 200:
            r.raw.decode_content = True
            image = Image.open(r.raw)
        else:
            irc.reply("Error: Invalid file type.", private=False, notice=False)
            return
        # open image and convert to grayscale
        start_time = time.time()
        self.source_colors = 0
        if image.mode == "RGBA":
            if bg == 99:
                newbg = 1
            else:
                newbg = bg
            image = Image.alpha_composite(
                Image.new("RGBA", image.size, rgbColors[newbg] + (255,)), image
            )
        if image.mode != "RGB":
            image = image.convert("RGB")
        try:
            os.remove(filename)
        except:
            pass
        # store dimensions
        W, H = image.size[0], image.size[1]
        # compute width of tile
        w = W / cols
        # compute tile height based on aspect ratio and scale
        if type == "1/2":
            scale = 1.0
        else:
            scale = 0.5
        h = w / scale
        # compute number of rows
        rows = int(H / h)
        if "resize" in optlist:
            resize = optlist.get("resize")
        else:
            resize = self.registryValue("resize", msg.args[0])
        if type != "no-color":
            image2 = image.resize((cols, rows), resize)
            if "s" in optlist:
                image2 = ImageEnhance.Color(image2).enhance(s)
            if quantize:
                image2 = image2.quantize(dither=None)
                image2 = image2.convert("RGB")
            colormap = np.array(image2)
            self.labmatches = {}
            if not self.registryValue("cacheColors"):
                self.matches = {}
        # ascii image is a list of character strings
        aimg = []
        if type == "1/2":
            k = 0
            for j in range(0, rows - 1, 2):
                # append an empty string
                aimg.append("")
                old_color1 = "99"
                old_color2 = "99"
                old_char = None
                for i in range(cols):
                    color1 = "%02d" % self.getColor(colormap[j][i].tolist(), speed)
                    color2 = "%02d" % self.getColor(colormap[j + 1][i].tolist(), speed)
                    if color1 == color2:
                        gsval = " "
                    else:
                        gsval = "▀"
                    if color1 == old_color1 and color2 == old_color2:
                        aimg[k] += gsval
                        old_char = gsval
                    elif gsval == " " and color1 == old_color2:
                        aimg[k] += " "
                        old_char = gsval
                    elif gsval == " " and color1 == old_color1 and old_char == "█":
                        aimg[k] = aimg[k][:-1]
                        aimg[k] += "\x0301,{0}  ".format(color1)
                        old_color1 = "01"
                        old_color2 = color1
                        old_char = gsval
                    elif gsval == " " and color1 == old_color1 and old_char == "^█":
                        aimg[k] = aimg[k][:-4]
                        aimg[k] += "\x0301,{0}  ".format(color1)
                        old_color1 = "01"
                        old_color2 = color1
                        old_char = gsval
                    elif (
                        gsval == " "
                        and color1 == old_color1
                        and old_char == "^^▀"
                        and "tops" not in optlist
                    ):
                        aimg[k] = aimg[k][:-7]
                        aimg[k] += "\x03{0},{1}▄ ".format(old_color2, color1)
                        old_color1 = old_color2
                        old_color2 = color1
                        old_char = gsval
                    elif (
                        gsval == " "
                        and color1 == old_color1
                        and old_char != "█"
                        and "tops" not in optlist
                    ):
                        aimg[k] += "█"
                        old_char = "█"
                    elif gsval == " " and "tops" not in optlist:
                        aimg[k] += "\x03{0}█".format(color1)
                        old_color1 = color1
                        old_char = "^█"
                    elif (
                        gsval != " "
                        and color1 == old_color1
                        and old_char == "^█"
                        and "tops" not in optlist
                    ):
                        aimg[k] = aimg[k][:-4]
                        aimg[k] += "\x03{0},{1} ▄".format(color2, color1)
                        old_color1 = color2
                        old_color2 = color1
                        old_char = "▄"
                    elif gsval != " " and color2 == old_color1 and old_char == "^█":
                        aimg[k] = aimg[k][:-4]
                        aimg[k] += "\x03{0},{1} ▀".format(color1, color2)
                        old_color1 = color1
                        old_color2 = color2
                        old_char = gsval
                    elif (
                        gsval != " "
                        and color1 == old_color2
                        and color2 == old_color1
                        and old_char == "^^▀"
                        and "tops" not in optlist
                    ):
                        aimg[k] = aimg[k][:-7]
                        aimg[k] += "\x03{0},{1}▄▀".format(color1, color2)
                        old_color1 = color1
                        old_color2 = color2
                        old_char = gsval
                    elif (
                        gsval != " "
                        and color1 == old_color1
                        and color2 != old_color2
                        and old_char == "^^▀"
                        and "tops" not in optlist
                    ):
                        aimg[k] = aimg[k][:-7]
                        aimg[k] += "\x03{0},{1}▄\x03{2}▄".format(
                            old_color2, color1, color2
                        )
                        old_color1 = color2
                        old_color2 = color1
                        old_char = "▄"
                    elif (
                        gsval != " "
                        and color1 == old_color1
                        and color2 != old_color2
                        and old_char == "^▀"
                        and "tops" not in optlist
                    ):
                        aimg[k] = aimg[k][:-4]
                        aimg[k] += "\x03{0},{1}▄\x03{2}▄".format(
                            old_color2, color1, color2
                        )
                        old_color1 = color2
                        old_color2 = color1
                        old_char = "▄"
                    elif (
                        gsval != " "
                        and color1 == old_color2
                        and color2 == old_color1
                        and "tops" not in optlist
                    ):
                        aimg[k] += "▄"
                        old_char = "▄"
                    elif (
                        gsval != " " and color1 == old_color2 and "tops" not in optlist
                    ):
                        aimg[k] += "\x03{0}▄".format(color2)
                        old_color1 = color2
                        old_char = "▄"
                    elif color1 != old_color1 and color2 == old_color2:
                        aimg[k] += "\x03{0}{1}".format(color1, gsval)
                        old_color1 = color1
                        if gsval == " ":
                            old_char = gsval
                        else:
                            old_char = "^▀"
                    else:
                        aimg[k] += "\x03{0},{1}{2}".format(color1, color2, gsval)
                        old_color1 = color1
                        old_color2 = color2
                        if gsval == " ":
                            old_char = gsval
                        else:
                            old_char = "^^▀"
                if "tops" in optlist:
                    aimg[k] = re.sub("\x03\d\d,(\d\d\s+\x03)", "\x0301,\g<1>", aimg[k])
                    aimg[k] = re.sub("\x03\d\d,(\d\d\s+$)", "\x0301,\g<1>", aimg[k])
                    aimg[k] = re.sub("\x03\d\d,(\d\d\s\x03)", "\x0301,\g<1>", aimg[k])
                aimg[k] = re.sub(
                    "\x0301,(\d\d)(\s+)\x03(\d\d)([^,])",
                    "\x03\g<3>,\g<1>\g<2>\g<4>",
                    aimg[k],
                )
                for i in range(0, 98):
                    i = "%02d" % i
                    aimg[k] = aimg[k].replace("{0}".format(i), "{0}".format(int(i)))
                k += 1
        else:
            if "chars" not in optlist and gscale != "\xa0":
                image = image.resize((cols, rows), resize)
                image = image.convert("L")
                lumamap = np.array(image)
            # generate list of dimensions
            char = 0
            for j in range(rows):
                # append an empty string
                aimg.append("")
                old_color = None
                for i in range(cols):
                    if "chars" not in optlist and gscale != "\xa0":
                        # get average luminance
                        avg = int(np.average(lumamap[j][i]))
                        # look up ascii char
                        gsval = gscale[int((avg * (len(gscale) - 1)) / 255)]
                    elif "chars" in optlist and gscale != "\xa0":
                        if char < len(gscale):
                            gsval = gscale[char]
                            char += 1
                        else:
                            char = 0
                            gsval = gscale[char]
                            char += 1
                    else:
                        gsval = "\xa0"
                    # get color value
                    if type != "no-color" and gscale != "\xa0" and i == 0:
                        color = self.getColor(colormap[j][i].tolist(), speed)
                        old_color = color
                        if bg != 99:
                            color = "{0},{1}".format(color, "{:02d}".format(int(bg)))
                        if gsval != "\xa0":
                            aimg[j] += "\x03{0}{1}".format(color, gsval)
                        else:
                            aimg[j] += "\x030,{0} ".format(int(color))
                    elif type == "no-color" and i == 0:
                        if bg != 99 and fg != 99:
                            aimg[j] += "\x03{0},{1}{2}".format(
                                "{:02d}".format(int(fg)),
                                "{:02d}".format(int(bg)),
                                gsval,
                            )
                        elif fg != 99:
                            aimg[j] += "\x03{0}{1}".format(
                                "{:02d}".format(int(fg)), gsval
                            )
                        elif bg != 99:
                            aimg[j] += "\x03{0},{1}{2}".format(
                                "{:02d}".format(int(fg)),
                                "{:02d}".format(int(bg)),
                                gsval,
                            )
                    elif type != "no-color" and gsval != " ":
                        color = self.getColor(colormap[j][i].tolist(), speed)
                        if color != old_color:
                            old_color = color
                            # append ascii char to string
                            if gsval != "\xa0":
                                if gsval.isdigit():
                                    color = "{:02d}".format(int(color))
                                    aimg[j] += "\x03{0}{1}".format(color, gsval)
                                else:
                                    aimg[j] += "\x03{0}{1}".format(int(color), gsval)
                            else:
                                aimg[j] += "\x030,{0} ".format(int(color))
                        else:
                            aimg[j] += "{0}".format(gsval)
                    else:
                        aimg[j] += "{0}".format(gsval)
        output = aimg
        self.stopped[channel] = False
        end_time = time.time()
        asyncio.run(self.reply(irc, output, channel, delay))
        if self.registryValue("pasteEnable", msg.args[0]):
            paste = ""
            for line in output:
                if not line.strip():
                    line = "\xa0"
                paste += line + "\n"
        if self.registryValue("showStats", msg.args[0]):
            longest = len(max(output, key=len).encode("utf-8"))
            render_time = "{0:.2f}".format(end_time - start_time)
            irc.reply(
                "[Source Colors: {0}, Render Time: {1} seconds, Longest Line: {2}"
                " bytes]".format(self.source_colors, render_time, longest),
                prefixNick=False,
            )
        if self.registryValue("pasteEnable", msg.args[0]):
            irc.reply(self.doPaste(url, paste), private=False, notice=False, to=channel)

    img = wrap(
        img,
        [
            optional("channel"),
            getopts(
                {
                    "w": "int",
                    "invert": "",
                    "fast": "",
                    "slow": "",
                    "16": "",
                    "99": "",
                    "83": "",
                    "delay": "float",
                    "resize": "int",
                    "quantize": "",
                    "no-quantize": "",
                    "chars": "text",
                    "bg": "int",
                    "fg": "int",
                    "ramp": "text",
                    "no-color": "",
                    "block": "",
                    "ascii": "",
                    "1/2": "",
                    "s": "float",
                    "tops": "",
                }
            ),
            "text",
        ],
    )

    def scroll(self, irc, msg, args, channel, optlist, url):
        """[<channel>] [--delay] <url>
        Play IRC art files from web links.
        """
        if not channel:
            channel = msg.args[0]
        if channel != msg.args[0] and not ircdb.checkCapability(msg.prefix, "admin"):
            irc.errorNoCapability("admin")
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        optlist = dict(optlist)
        self.stopped[channel] = False
        if "delay" in optlist and ircdb.checkCapability(msg.prefix, "admin"):
            delay = optlist.get("delay")
        else:
            delay = self.registryValue("delay", msg.args[0])
        if url.startswith("https://paste.ee/p/"):
            url = url.replace("https://paste.ee/p/", "https://paste.ee/r/")
        elif url.startswith("https://pastebin.com/") and "/raw/" not in url:
            url = url.replace("https://pastebin.com/", "https://pastebin.com/raw/")
        ua = random.choice(self.agents)
        header = {"User-Agent": ua}
        try:
            r = requests.get(url, headers=header, stream=True, timeout=10)
            r.raise_for_status()
        except (
            requests.exceptions.RequestException,
            requests.exceptions.HTTPError,
        ) as e:
            log.debug("TextArt: error retrieving data for scroll: {0}".format(e))
            return
        if "text/plain" in r.headers["content-type"]:
            try:
                file = r.content.decode().replace("\r\n", "\n")
            except:
                file = r.text.replace("\r\n", "\n")
        else:
            irc.reply("Invalid file type.", private=False, notice=False)
            return
        output = file.splitlines()
        asyncio.run(self.reply(irc, output, channel, delay))

    scroll = wrap(scroll, [optional("channel"), getopts({"delay": "float"}), "text"])

    def a2m(self, irc, msg, args, channel, optlist, url):
        """[<channel>] [--delay] [--l] [--r] [--n] [--p] [--t] [--w] <url>
        Convert ANSI files to IRC formatted text. https://github.com/tat3r/a2m
        """
        if not channel:
            channel = msg.args[0]
        if channel != msg.args[0] and not ircdb.checkCapability(msg.prefix, "admin"):
            irc.errorNoCapability("admin")
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        optlist = dict(optlist)
        opts = ""
        if "l" in optlist:
            l = optlist.get("l")
            opts += "-l {0} ".format(l)
        if "r" in optlist:
            r = optlist.get("r")
            opts += "-r {0} ".format(r)
        if "n" in optlist:
            n = optlist.get("n")
            opts += "-n {0}".format(n)
        if "p" in optlist:
            opts += "-p "
        if "t" in optlist:
            t = optlist.get("t")
            opts += "-t {0} ".format(t)
        if "w" in optlist:
            w = optlist.get("w")
            opts += "-w {0} ".format(w)
        else:
            opts += "-w 80 "
        if "delay" in optlist and ircdb.checkCapability(msg.prefix, "admin"):
            delay = optlist.get("delay")
        else:
            delay = self.registryValue("delay", msg.args[0])
        ua = random.choice(self.agents)
        header = {"User-Agent": ua}
        try:
            r = requests.get(url, stream=True, headers=header, timeout=10)
            r.raise_for_status()
        except (
            requests.exceptions.RequestException,
            requests.exceptions.HTTPError,
        ) as e:
            log.debug("TextArt: error retrieving data for a2m: {0}".format(e))
            return
        try:
            if (
                "text/plain" in r.headers["content-type"]
                or "application/octet-stream" in r.headers["content-type"]
                and int(r.headers["content-length"]) < 1000000
            ):
                path = os.path.dirname(os.path.abspath(__file__))
                filepath = "{0}/tmp".format(path)
                filename = "{0}/{1}".format(filepath, url.split("/")[-1])
                open(filename, "wb").write(r.content.replace(b";5;", b";"))
                try:
                    output = pexpect.run(
                        "a2m {0} {1}".format(opts.strip(), str(filename))
                    )
                    try:
                        os.remove(filename)
                    except:
                        pass
                except:
                    irc.reply(
                        "Error. Have you installed A2M? https://github.com/tat3r/a2m",
                        private=False,
                        notice=False,
                    )
                    return
            else:
                irc.reply("Invalid file type.")
                return
        except:
            irc.reply("Invalid file type.")
            return
        self.stopped[channel] = False
        output = re.sub("(\x03(\d+).*)\x03,", "\g<1>\x03\g<2>,", output.decode())
        output = output.splitlines()
        asyncio.run(self.reply(irc, output, channel, delay))
        if self.registryValue("pasteEnable", msg.args[0]):
            paste = ""
            for line in output:
                if not line.strip():
                    line = "\xa0"
                paste += line + "\n"
        if self.registryValue("pasteEnable", msg.args[0]):
            irc.reply(self.doPaste(url, paste), private=False, notice=False, to=channel)

    a2m = wrap(
        a2m,
        [
            optional("channel"),
            getopts(
                {
                    "l": "int",
                    "r": "int",
                    "t": "int",
                    "w": "int",
                    "p": "",
                    "delay": "float",
                }
            ),
            "text",
        ],
    )

    def p2u(self, irc, msg, args, channel, optlist, url):
        """[<channel>] [--b] [--f] [--p] [--s] [--t] [--w] [--delay] <url>
        Picture to Unicode. https://git.trollforge.org/p2u/about/
        """
        if not channel:
            channel = msg.args[0]
        if channel != msg.args[0] and not ircdb.checkCapability(msg.prefix, "admin"):
            irc.errorNoCapability("admin")
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        optlist = dict(optlist)
        opts = ""
        if "b" in optlist:
            b = optlist.get("b")
            opts += "-b {0} ".format(b)
        if "f" in optlist:
            f = optlist.get("f")
            opts += "-f {0} ".format(f)
        else:
            opts += "-f m "
        if "p" in optlist:
            p = optlist.get("p")
            opts += "-p {0} ".format(p)
        else:
            opts += "-p x "
        if "s" in optlist:
            s = optlist.get("s")
            opts += "-s {0} ".format(s)
        if "t" in optlist:
            t = optlist.get("t")
            opts += "-t {0} ".format(t)
        if "w" in optlist:
            w = optlist.get("w")
            opts += "-w {0} ".format(w)
        else:
            w = self.registryValue("blockWidth", msg.args[0])
            opts += "-w {0} ".format(w)
        if "delay" in optlist and ircdb.checkCapability(msg.prefix, "admin"):
            delay = optlist.get("delay")
        else:
            delay = self.registryValue("delay", msg.args[0])
        path = os.path.dirname(os.path.abspath(__file__))
        filepath = "{0}/tmp".format(path)
        filename = "{0}/{1}".format(filepath, url.split("/")[-1])
        ua = random.choice(self.agents)
        header = {"User-Agent": ua}
        image_formats = ("image/png", "image/jpeg", "image/jpg", "image/gif")
        try:
            r = requests.get(url, stream=True, headers=header, timeout=10)
            r.raise_for_status()
        except (
            requests.exceptions.RequestException,
            requests.exceptions.HTTPError,
        ) as e:
            log.debug("TextArt: error retrieving data for p2u: {0}".format(e))
            return
        if r.headers["content-type"] in image_formats and r.status_code == 200:
            with open("{0}".format(filename), "wb") as f:
                f.write(r.content)
            try:
                output = pexpect.run(
                    "p2u -f m {0} {1}".format(opts.strip(), str(filename))
                )
                try:
                    os.remove(filename)
                except:
                    pass
            except:
                irc.reply(
                    "Error. Have you installed p2u? https://git.trollforge.org/p2u",
                    private=False,
                    notice=False,
                )
                return
        else:
            irc.reply("Invalid file type.", private=False, notice=False)
            return
        self.stopped[channel] = False
        output = output.decode().splitlines()
        output = [re.sub("^\x03 ", " ", line) for line in output]
        asyncio.run(self.reply(irc, output, channel, delay))
        if self.registryValue("pasteEnable", msg.args[0]):
            paste = ""
            for line in output:
                if not line.strip():
                    line = "\xa0"
                paste += line + "\n"
        if self.registryValue("pasteEnable", msg.args[0]):
            irc.reply(self.doPaste(url, paste), private=False, notice=False, to=channel)
        else:
            irc.reply(
                "Unexpected file type or link format", private=False, notice=False
            )

    p2u = wrap(
        p2u,
        [
            optional("channel"),
            getopts(
                {
                    "b": "int",
                    "f": "text",
                    "p": "text",
                    "s": "int",
                    "t": "int",
                    "w": "int",
                    "delay": "float",
                }
            ),
            "text",
        ],
    )

    def tdf(self, irc, msg, args, channel, optlist, text):
        """[<channel>] [--f] [--j] [--w] [--e] [--r] [--i][--delay] <text>
        Text to TheDraw ANSI Fonts. http://www.roysac.com/thedrawfonts-tdf.html
        --f [font] Specify font file used.
        --j l|r|c  Justify left, right, or center.  Default is left.
        --w n      Set screen width.  Default is 80.
        --c a|m    Color format ANSI or mirc.  Default is ANSI.
        --i        Print font details.
        --r        Use random font.
        """
        if not channel:
            channel = msg.args[0]
        if channel != msg.args[0] and not ircdb.checkCapability(msg.prefix, "admin"):
            irc.errorNoCapability("admin")
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        if len(text) > self.registryValue("maxLength", msg.channel):
            return
        if len(text.split(" ")) > self.registryValue("maxWords", msg.channel):
            return
        optlist = dict(optlist)
        opts = ""
        if "f" in optlist:
            f = optlist.get("f")
            opts += "-f {0} ".format(f.lower())
        else:
            opts += "-r "
        if "j" in optlist:
            j = optlist.get("j")
            opts += "-j {0} ".format(j)
        if "w" in optlist:
            w = optlist.get("w")
            opts += "-w {0} ".format(w)
        else:
            opts += "-w 80 "
        if "e" in optlist:
            e = optlist.get("e")
            opts += "-e {0} ".format(e)
        if "r" in optlist:
            opts += "-r "
        if "delay" in optlist and ircdb.checkCapability(msg.prefix, "admin"):
            delay = optlist.get("delay")
        else:
            delay = self.registryValue("delay", msg.args[0])
        if "i" in optlist:
            opts += "-i "
        try:
            output = pexpect.run(
                "tdfiglet -c m {0} {1}".format(opts.strip(), r"{}".format(text))
            )
        except:
            irc.reply(
                "Error. Have you installed tdfiglet? https://github.com/tat3r/tdfiglet",
                private=False,
                notice=False,
            )
            return
        self.stopped[channel] = False
        output = output.decode().replace("\r\r\n", "\r\n")
        output = re.sub("\x03\x03\s*", "\x0F ", output)
        output = re.sub("\x0F\s*\x03$", "", output)
        output = output.splitlines()
        asyncio.run(self.reply(irc, output, channel, delay))
        if self.registryValue("pasteEnable", msg.args[0]):
            paste = ""
            for line in output:
                if not line.strip():
                    line = "\xa0"
                paste += line + "\n"
        if self.registryValue("pasteEnable", msg.args[0]):
            irc.reply(
                self.doPaste(text, paste), private=False, notice=False, to=channel
            )

    tdf = wrap(
        tdf,
        [
            optional("channel"),
            getopts(
                {
                    "f": "text",
                    "j": "text",
                    "w": "int",
                    "e": "text",
                    "r": "",
                    "i": "",
                    "delay": "float",
                }
            ),
            "text",
        ],
    )

    def toilet(self, irc, msg, args, channel, optlist, text):
        """[<channel>] [--f fontname] [--F filter1,filter2,etc.] [--w] [--delay] <text>
        Text to toilet figlets. -f to select font. -F to select filters. Separate multiple filters with a comma.
        """
        if not channel:
            channel = msg.args[0]
        if channel != msg.args[0] and not ircdb.checkCapability(msg.prefix, "admin"):
            irc.errorNoCapability("admin")
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        if len(text) > self.registryValue("maxLength", msg.channel):
            return
        if len(text.split(" ")) > self.registryValue("maxWords", msg.channel):
            return
        optlist = dict(optlist)
        opts = ""
        if "f" in optlist:
            f = optlist.get("f")
            opts += "-f {0} ".format(f)
        if "F" in optlist:
            filter = optlist.get("F")
            if "," in filter:
                filter = filter.split(",")
                for i in range(len(filter)):
                    opts += "-F {0} ".format(filter[i])
            else:
                opts += "-F {0} ".format(filter)
        if "w" in optlist:
            w = optlist.get("w")
            opts += "-w {0} ".format(w)
        elif "W" in optlist:
            opts += "-W "
        else:
            opts += "-w 100 "
        if "s" in optlist:
            opts += "-s "
        elif "k" in optlist:
            opts += "-k "
        elif "o" in optlist:
            opts += "-o "
        elif "S" in optlist:
            opts += "-S "
        if "delay" in optlist and ircdb.checkCapability(msg.prefix, "admin"):
            delay = optlist.get("delay")
        else:
            delay = self.registryValue("delay", msg.args[0])
        try:
            output = pexpect.run("toilet --irc {0} {1}".format(opts.strip(), text))
        except:
            irc.reply("Error. Have you installed toilet?", private=False, notice=False)
            return
        self.stopped[channel] = False
        output = output.decode().replace("\r\r\n", "\r\n")
        output = output.splitlines()
        asyncio.run(self.reply(irc, output, channel, delay))
        if self.registryValue("pasteEnable", msg.args[0]):
            paste = ""
            for line in output:
                if not line.strip():
                    line = "\xa0"
                paste += line + "\n"
        if self.registryValue("pasteEnable", msg.args[0]):
            irc.reply(
                self.doPaste(text, paste), private=False, notice=False, to=channel
            )

    toilet = wrap(
        toilet,
        [
            optional("channel"),
            getopts(
                {
                    "f": "text",
                    "F": "text",
                    "s": "",
                    "S": "",
                    "k": "",
                    "w": "int",
                    "W": "",
                    "o": "",
                    "delay": "float",
                }
            ),
            "text",
        ],
    )

    def fonts(self, irc, msg, args, optlist):
        """[--toilet]
        List figlets. Default list are tdf fonts. --toilet for toilet fonts
        """
        optlist = dict(optlist)
        if "toilet" in optlist:
            try:
                reply = ", ".join(sorted(os.listdir("/usr/share/figlet")))
                irc.reply(reply, prefixNick=False)
            except:
                irc.reply("Sorry, unable to access font directory /usr/share/figlet")
        else:
            try:
                reply = ", ".join(
                    sorted(os.listdir("/usr/local/share/tdfiglet/fonts/"))
                )
                irc.reply(
                    "http://www.roysac.com/thedrawfonts-tdf.html", prefixNick=False
                )
                irc.reply(reply, prefixNick=False)
            except FileNotFoundError:
                reply = ", ".join(sorted(os.listdir("/usr/share/figlet")))
                irc.reply(reply, prefixNick=False)
            except:
                irc.reply(
                    "Sorry, unable to access font directories"
                    " /usr/local/share/tdfiglet/fonts/ or /usr/share/figlet"
                )

    fonts = wrap(fonts, [getopts({"toilet": ""})])

    def wttr(self, irc, msg, args, channel, optlist, location):
        """[<channel>] [--16] [--99] <location/moon>
        IRC art weather report from wttr.in for <location>.
        --16 for 16 colors (default).
        --99 for 99 colors.
        Get moon phase with 'wttr moon'.
        <location>?u (use imperial units).
        <location>?m (metric).
        <location>?<1-3> (number of days)
        """
        if not channel:
            channel = msg.args[0]
        if channel != msg.args[0] and not ircdb.checkCapability(msg.prefix, "admin"):
            irc.errorNoCapability("admin")
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        if "format=j" in location.lower():
            return
        optlist = dict(optlist)
        if "delay" in optlist and ircdb.checkCapability(msg.prefix, "admin"):
            delay = optlist.get("delay")
        else:
            delay = self.registryValue("delay", msg.args[0])
        if "16" in optlist:
            self.colors = 16
        elif "99" in optlist:
            self.colors = 99
        else:
            self.colors = self.registryValue("colors", msg.args[0])
        file = requests.get("http://wttr.in/{0}".format(location), timeout=10)
        output = file.content.decode()
        output = self.ansi2irc(output)
        output = re.sub("⚡", "☇ ", output)
        output = re.sub("‘‘", "‘ ", output)
        output = re.sub("\n\nFollow.*$", "", output)
        self.stopped[channel] = False
        output = output.splitlines()
        output = [line.strip("\x0F") for line in output]
        asyncio.run(self.reply(irc, output, channel, delay))
        if self.registryValue("pasteEnable", msg.args[0]):
            paste = ""
            for line in output:
                if not line.strip():
                    line = "\xa0"
                paste += line + "\n"
        if self.registryValue("pasteEnable", msg.args[0]):
            irc.reply(
                self.doPaste(location, paste), private=False, notice=False, to=channel
            )

    wttr = wrap(
        wttr,
        [
            optional("channel"),
            getopts({"delay": "float", "16": "", "99": "", "fast": "", "slow": ""}),
            "text",
        ],
    )

    def rate(self, irc, msg, args, channel, optlist, coin):
        """[<channel>] [--16] [--99] [--sub <text>] [coin]
        Crypto exchange rate info from rate.sx. http://rate.sx/:help. Use --sub to
        set subdomain e.g. eur, btc, etc. Get a graph with [coin] e.g. 'rate btc'.
        --16 for 16 colors (default).
        --99 for 99 colors.
        """
        if not channel:
            channel = msg.args[0]
        if channel != msg.args[0] and not ircdb.checkCapability(msg.prefix, "admin"):
            irc.errorNoCapability("admin")
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        optlist = dict(optlist)
        if "delay" in optlist and ircdb.checkCapability(msg.prefix, "admin"):
            delay = optlist.get("delay")
        else:
            delay = self.registryValue("delay", msg.args[0])
        if "16" in optlist:
            self.colors = 16
        elif "99" in optlist:
            self.colors = 99
        else:
            self.colors = self.registryValue("colors", msg.args[0])
        if "sub" in optlist:
            sub = optlist.get("sub")
        else:
            sub = "usd"
        if not coin:
            coin = ""
        file = requests.get("http://{0}.rate.sx/{1}".format(sub, coin), timeout=10)
        output = file.content.decode()
        output = self.ansi2irc(output)
        output = output.replace("\x1b(B", "")
        output = re.sub(r"\n\x0307NEW FEATURE:.*\n.*", "", output).strip()
        output = output.splitlines()
        output = [line.strip("\x0F") for line in output]
        self.stopped[channel] = False
        asyncio.run(self.reply(irc, output, channel, delay))
        if self.registryValue("pasteEnable", msg.args[0]):
            paste = ""
            for line in output:
                if not line.strip():
                    line = "\xa0"
                paste += line + "\n"
        if self.registryValue("pasteEnable", msg.args[0]):
            irc.reply(
                self.doPaste(coin, paste), private=False, notice=False, to=channel
            )

    rate = wrap(
        rate,
        [
            optional("channel"),
            getopts(
                {
                    "delay": "float",
                    "16": "",
                    "99": "",
                    "sub": "text",
                    "fast": "",
                    "slow": "",
                }
            ),
            optional("text"),
        ],
    )

    def fortune(self, irc, msg, args, channel, optlist):
        """[<channel>]
        Returns random art fortune from http://www.asciiartfarts.com/fortune.txt
        """
        if not channel:
            channel = msg.args[0]
        if channel != msg.args[0] and not ircdb.checkCapability(msg.prefix, "admin"):
            irc.errorNoCapability("admin")
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        optlist = dict(optlist)
        if "delay" in optlist and ircdb.checkCapability(msg.prefix, "admin"):
            delay = optlist.get("delay")
        else:
            delay = self.registryValue("delay", msg.args[0])
        self.stopped[channel] = False
        data = requests.get("http://www.asciiartfarts.com/fortune.txt", timeout=10)
        fortunes = data.content.decode().split("%\n")
        fortune = random.randrange(0, len(fortunes))
        output = fortunes[fortune].splitlines()
        asyncio.run(self.reply(irc, output, channel, delay))

    fortune = wrap(fortune, [optional("channel"), getopts({"delay": "float"})])

    def mircart(self, irc, msg, args, channel, optlist, search):
        """[<channel>] (search text)
        Search https://mircart.org/ and scroll first result
        """
        if not channel:
            channel = msg.args[0]
        if channel != msg.args[0] and not ircdb.checkCapability(msg.prefix, "admin"):
            irc.errorNoCapability("admin")
            return
        if not irc.isChannel(channel):
            channel = msg.nick
        optlist = dict(optlist)
        if "delay" in optlist and ircdb.checkCapability(msg.prefix, "admin"):
            delay = optlist.get("delay")
        else:
            delay = self.registryValue("delay", msg.args[0])
        self.stopped[channel] = False
        ua = random.choice(self.agents)
        header = {"User-Agent": ua}
        data = requests.get(
            "https://mircart.org/?s={0}".format(search), headers=header, timeout=10
        )
        if not data:
            irc.reply("Error: No results found for {0}".format(search))
            return
        soup = BeautifulSoup(data.content)
        url = soup.find(href=re.compile(".txt"))
        if not url:
            irc.reply("Error: No results found for {0}".format(search))
            return
        data = requests.get(url.get("href"), headers=header, timeout=10)
        try:
            output = data.content.decode()
        except:
            output = data.text
        output = output.splitlines()
        asyncio.run(self.reply(irc, output, channel, delay))
        irc.reply(url.get("href"))

    mircart = wrap(mircart, [optional("channel"), getopts({"delay": "float"}), "text"])

    def cq(self, irc, msg, args):
        """
        Stop the scroll.
        """
        channel = msg.args[0]
        if not irc.isChannel(channel):
            channel = msg.nick
        self.stopped.setdefault(channel, None)
        if not self.stopped[channel]:
            irc.reply("Stopping.")
        self.stopped[channel] = True

    cq = wrap(cq)

    def codes(self, irc, msg, args, optlist):
        """
        Show a grid of IRC color codes.
        """
        channel = msg.args[0]
        if not irc.isChannel(channel):
            channel = msg.nick
        optlist = dict(optlist)
        if "delay" in optlist and ircdb.checkCapability(msg.prefix, "admin"):
            delay = optlist.get("delay")
        else:
            delay = self.registryValue("delay", msg.args[0])
        output = []
        output.append(
            "\x031,0000\x031,0101\x031,0202\x031,0303\x031,0404\x031,0505\x031,0606\x031,0707\x031,0808\x031,0909\x031,1010\x031,1111\x031,1212\x031,1313\x031,1414\x031,1515",
        )
        output.append(
            "\x031,1616\x031,1717\x031,1818\x031,1919\x031,2020\x031,2121\x031,2222\x031,2323\x031,2424\x031,2525\x031,2626\x031,2727",
        )
        output.append(
            "\x031,2828\x031,2929\x031,3030\x031,3131\x031,3232\x031,3333\x031,3434\x031,3535\x031,3636\x031,3737\x031,3838\x031,3939",
        )
        output.append(
            "\x031,4040\x031,4141\x031,4242\x031,4343\x031,4444\x031,4545\x031,4646\x031,4747\x031,4848\x031,4949\x031,5050\x031,5151",
        )
        output.append(
            "\x031,5252\x031,5353\x031,5454\x031,5555\x031,5656\x031,5757\x031,5858\x031,5959\x031,6060\x031,6161\x031,6262\x031,6363",
        )
        output.append(
            "\x031,6464\x031,6565\x031,6666\x031,6767\x031,6868\x031,6969\x031,7070\x031,7171\x031,7272\x031,7373\x031,7474\x031,7575",
        )
        output.append(
            "\x031,7676\x031,7777\x031,7878\x031,7979\x031,8080\x031,8181\x031,8282\x031,8383\x031,8484\x031,8585\x031,8686\x031,8787",
        )
        output.append(
            "\x031,8888\x031,8989\x031,9090\x031,9191\x031,9292\x031,9393\x031,9494\x031,9595\x031,9696\x031,9797\x031,9898\x031,9999",
        )
        asyncio.run(self.reply(irc, output, channel, delay))

    codes = wrap(codes, [getopts({"delay": "float"})])


Class = TextArt
