import sys

from lexer import Lexer

class SyntaxError(Exception):
    pass

class Parser(object):
    def __init__(self):
        self.tokens = None
        self.current = 0
        self.skiplabel = {}
        self.nskip = 0

        self.rules = [
            ("BLANK", r"[ \t\r\n]+"),
            ("COMMENT", r";.*"),
            ("NUM", r"-?[0-9]+"),
            ("VARNUM", r"%\w*"),
            ("VARSTR", r"\$\w*"),
            ("LABEL", r"\*\w*"),
            ("SKIP", (r"skip\s*-?[0-9]+", self.skip_cb)),
            ("COLOR", r"#[a-fA-F0-9]{6}|white|black"),
            ("IDENTIFIER", r"[a-zA-Z_]\w*|!w|!sd|!s|!d"),
            ("STR", r"\".*\""),
            ("TEXT", r"`[^`\n]*`?|\\"),
            ("COMMA",   r","),
            ("SEP",   r":"),
            ("EQ",   r"==?"),
            ("NEQ",   r"!="),
            ("LE",   r"<="),
            ("LT",   r"<"),
            ("GE",   r">="),
            ("GT",   r">"),
            ("AND",   r"&&?"),
            ("OR",   r"\|\|?"),
            ("PLUS",   r"\+"),
        ]
 
    def skip_cb(self, scanner, token, line):
        skip = int(token.replace('skip', ''))
        skipto = line + skip
        if not skipto in self.skiplabel:
            self.skiplabel[skipto] = "__skip__%i" % self.nskip
            self.nskip += 1

        return skip

    def tokenize(self, content):
        lex = Lexer(self.rules, case_sensitive=False)
        self.tokens = [token for token in lex.scan(content) if token is not None and token.type != "COMMENT"]

        # Preprocessing:
        while True:
            token = self.read()
            if token is None:
                break

        self.current = 0

    def read(self, tokenType=None, mandatory=True):
        if self.current >= len(self.tokens):
            return None

        token = self.tokens[self.current]

        if tokenType is None or (type(tokenType).__name__=='list' and token.type in tokenType) or token.type == tokenType:
            self.current += 1
            return token
        else:
            if mandatory:
                raise SyntaxError("Expecting %s on %i got %s" % (tokenType, token.line, token.type))
            else:
                return None

class Translator(object):
    def __init__(self, parser, out):
        self.parser = parser
        self.out = out
        self.nimage = 0
        self.images = {}

    def translate(self):
        skipdone = {}

        self.out.write('label start:\n')
        while True:
            token = self.parser.read()
            if token is None:
                break

            for skipto in self.parser.skiplabel.keys():
                if not skipto in skipdone and skipto <= token.line:
                    self.out.write('label %s:\n' % self.parser.skiplabel[skipto])
                    skipdone[skipto] = True
                    break
                
            if token.type == "IDENTIFIER":
                self.read_command(token)
            elif token.type == "LABEL":
                self.out.write('label %s:\n' % token.value.replace('*', ''))
            elif token.type == "TEXT":
                self.read_text(token)
            elif token.type == "SKIP":
                self.read_skip(token)
            elif token.type == "SEP":
                pass
            else:
                sys.stderr.write('Invalid token: %s at %d\n' % (token.type, token.line))

        self.out.write('\n')
        self.out.write('init:\n')
        self.out.write('  $ narrator = Character(None, kind=nvl)\n')
        self.out.write('  $ autoclick = 3600\n\n')

        for img in self.images.keys():
            if img.startswith('"#'):
                self.out.write('  image bg %s = %s\n' % (self.images[img], img.replace('\\', '/')))
            else:
                self.out.write('  image bg %s = im.FactorScale(%s, 1.25, 1.25)\n' % (self.images[img], img.replace('\\', '/')))

    def read_text(self, token):
        term = ''
        text = token.value.replace('`', '')

        text = text + '{nw}'
        text = text.replace('@', '{w=%(autoclick)d}')
        text = text.replace('\\', '{w=%(autoclick)d}')
        text = self.escape_text(text)
        self.out.write('"%s"\n' % text)
        if '\\' in token.value:
            self.out.write('nvl clear\n')

    def escape_text(self, text):
        escaped = ''
        leading = True
        for c in text:
            if c == ' ' and leading:
                escaped += '\ '
            else:
                escaped += c
                leading = False

        return escaped.replace('"', '\\"')

    def read_skip(self, token):
        skipto = token.line + token.value
        self.out.write('jump %s\n' % self.parser.skiplabel[skipto])

    def read_command(self, token):
        if token.value == 'numalias':
            self.cmd_numalias()
        elif token.value == 'stralias':
            self.cmd_stralias()
        elif token.value == 'goto':
            self.cmd_goto()
        elif token.value == 'gosub':
            self.cmd_gosub()
        elif token.value == 'bg':
            self.cmd_bg()
        elif token.value == 'br':
            self.cmd_br()
        elif token.value == 'autoclick':
            self.cmd_autoclick()
        elif token.value == 'setwindow':
            self.cmd_setwindow()
        elif token.value == 'windoweffect':
            self.cmd_windoweffect()
        elif token.value == 'setcursor':
            self.cmd_setcursor()
        elif token.value == 'play':
            self.cmd_play()
        elif token.value == 'playstop':
            self.cmd_playstop()
        elif token.value == 'return':
            self.cmd_return()
        elif token.value == '!w':
            self.cmd_w()
        else:
            sys.stderr.write('Unknown command: %s\n' % token.value)

    def cmd_numalias(self):
        # IDENTIFIER,NUM
        alias = self.parser.read("IDENTIFIER")
        self.parser.read("COMMA")
        val = self.parser.read("NUM")

    def cmd_stralias(self):
        # IDENTIFIER,STR
        alias = self.parser.read("IDENTIFIER")
        self.parser.read("COMMA")
        val = self.parser.read("STR")

    def cmd_goto(self):
        # LABEL
        label = self.parser.read("LABEL").value
        self.out.write('jump %s\n' % label.replace('*', ''))

    def cmd_gosub(self):
        # LABEL
        label = self.parser.read("LABEL").value
        self.out.write('call %s\n' % label.replace('*', ''))

    def cmd_bg(self):
        bg = self.parser.read(["STR", "COLOR"])
        self.parser.read("COMMA")
        effect = self.parser.read(["NUM", "VARNUM"])

        img = bg.value
        if bg.type == "COLOR":
            img = '"%s"' % img

        if not img in self.images:
            self.images[img] = "__image__%i" % self.nimage
            self.nimage += 1

        self.out.write('scene bg %s\n' % self.images[img])

    def cmd_br(self):
        self.out.write('".{fast}{nw}"\n')

    def cmd_autoclick(self):
        # NUM
        autoclick = self.parser.read("NUM").value
        if autoclick == '0':
            autoclick = '3600000'
        self.out.write('$ autoclick=%s/1000\n' % autoclick)

    def cmd_setwindow(self):
        # NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,COLOR,NUM,NUM,NUM,NUM
        # NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,STR,NUM,NUM
        for i in range(11):
            self.parser.read("NUM")
            self.parser.read("COMMA")

        bg = self.parser.read(["STR", "COLOR"])

        img = bg.value
        if bg.type == "COLOR":
            img = '"%s"' % img

        if not img in self.images:
            self.images[img] = '__image__%i' % self.nimage
            self.nimage += 1

        self.out.write('scene bg %s\n' % self.images[img])

        if bg.type == "STR":
            r = 2
        else:
            r = 4

        for i in range(r):
            self.parser.read("COMMA")
            self.parser.read("NUM")

    def cmd_windoweffect(self):
        # NUM[,NUM[,STR]]
        self.parser.read("NUM")
        comma = self.parser.read("COMMA", mandatory=False)
        if comma is not None:
            self.parser.read("NUM")
            comma = self.parser.read("COMMA", mandatory=False)
            if comma is not None:
                self.parser.read("STR")

    def cmd_setcursor(self):
        # NUM,STR,NUM,NUM
        self.parser.read("NUM")
        self.parser.read("COMMA")
        self.parser.read("STR")
        self.parser.read("COMMA")
        self.parser.read("NUM")
        self.parser.read("COMMA")
        self.parser.read("NUM")

    def cmd_play(self):
        # STR
        track = self.parser.read("STR").value.replace('*', '').replace('"', '')

        if len(track) == 1:
            track = '0' + track

        self.out.write('play music "CD/track%s.ogg"\n' % track)

    def cmd_playstop(self):
        self.out.write('stop music\n')

    def cmd_return(self):
        self.out.write('return\n')

    def cmd_w(self):
        # NUM
        wait = self.parser.read("NUM")
        self.out.write('$ renpy.pause(%s/1000)\n' % wait.value)

if __name__ == '__main__':
    parser = Parser()
    input = open(sys.argv[1], 'r', encoding='sjis')

    parser.tokenize(input.read())

    input.close()

    translator = Translator(parser, sys.stdout)

    translator.translate()

