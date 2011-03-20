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
        self.numaliases = {}
        self.straliases = {}

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

        self.current = 0

    def escape(self, token):
        if token.type == "STR":
            return token.value.replace('\\', '/')
        elif token.type == "IDENTIFIER":
            if token.value in self.numaliases:
                return 'ns_na_%s' % token.value
            elif token.value in self.straliases:
                return 'ns_sa_%s' % token.value
            else:
                return token.value
        elif token.type == "VARNUM":
            var = token.value.replace('%', '')
            try:
                return int(var)
            except ValueError:
                return 'ns_na_%s' % var
        elif token.type == "VARSTR":
            var = token.value.replace('$', '')
            try:
                return int(var)
            except ValueError:
                return 'ns_na_%s' % var
        elif token.type == "COLOR":
            return '"%s"' % token.value
        elif token.type == 'AND':
            return 'and'
        elif token.type == 'OR':
            return 'or'
        else:
            return token.value

    def read(self, tokenType=None, mandatory=True):
        if self.current >= len(self.tokens):
            return None

        token = self.tokens[self.current]

        if tokenType is None or (type(tokenType).__name__=='list' and token.type in tokenType) or token.type == tokenType:
            self.current += 1
            token.escaped = self.escape(token)
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
        self.variables = {}
        self.indent = 0
        self.vars = dict(
            autoclick = 'ns_autoclick',
            images_size = 'ns_images_size',
            numvars = 'ns_numvars',
            rh = 'ns_rh',
            rw = 'ns_rw',
            salpha = 'ns_salpha',
            salphatrans = 'ns_salphatrans',
            spos = 'ns_spos',
            sprites = 'ns_sprites',
            strvars = 'ns_strvars',
            xpos = 'ns_xpos',
            ypos = 'ns_ypos',
        )


    def translate(self):
        skipdone = {}

        self.write_statement('label start:')
        self.indent += 1
        while True:
            token = self.parser.read()
            if token is None:
                break

            for skipto in self.parser.skiplabel.keys():
                if not skipto in skipdone and skipto <= token.line:
                    self.write_statement('\nlabel %s:' % self.parser.skiplabel[skipto])
                    skipdone[skipto] = True
                    break

            self.handle_token(token)

        self.write_statement('')
        self.write_statement('init 2:')
        self.indent += 1
        self.generate_images()

    def generate_images(self):
        for (pos, img) in self.images.keys():
            if img.type == 'COLOR':
                self.write_statement('image %s %s = %s' % (pos, self.images[(pos, img)], img.escaped))
            elif img.type == 'VARSTR':
                imgDef = ''
                for val in self.variables[img]:
                    if imgDef != '':
                        imgDef += ', '
                    if val.value.startswith('":a;'):
                        imgDef += '\'%s==%s\', alpha_blend(%s, "%s")' % (self.get_var(img), val.escaped, val.escaped.replace(':a;', '').lower(), self.images[(pos, img)])
                    else:
                        imgDef += '\'%s==%s\', scale(%s)' % (self.get_var(img), val.escaped, val.escaped.lower())
                self.write_statement('image %s %s = ConditionSwitch(%s)' %  (pos, self.images[(pos, img)], imgDef))
            else:
                if img.value.startswith('":a;'):
                    self.write_statement('image %s %s = alpha_blend(%s, "%s")' % (pos, self.images[(pos, img)], img.escaped.replace(':a;', '').lower(), self.images[(pos, img)]))
                else:
                    self.write_statement('image %s %s = scale(%s)' % (pos, self.images[(pos, img)], img.escaped.lower()))

    def handle_token(self, token):
        if token.type == "IDENTIFIER":
            self.read_command(token)
        elif token.type == "LABEL":
            self.indent = 0
            self.write_statement('\nlabel %s:' % token.value.replace('*', ''))
            self.indent = 1
        elif token.type == "TEXT":
            self.read_text(token)
        elif token.type == "SKIP":
            self.read_skip(token)
        elif token.type == "SEP":
            pass
        else:
            sys.stderr.write('Invalid token: %s at %d\n' % (token.type, token.line))

    def write_statement(self, line, newline=True):
        for i in range(self.indent):
            self.out.write('  ')
        self.out.write(line)
        if newline:
            self.out.write('\n')

    def read_text(self, token):
        term = ''
        text = token.value.replace('`', '')

        text = text + '{nw}'
        text = text.replace('@', '{w=%%(%s)d}' % self.vars['autoclick'])
        text = text.replace('\\', '{w=%%(%s)d}' % self.vars['autoclick'])
        text = self.escape_text(text)
        self.write_statement('"%s"' % text)
        if '\\' in token.value:
            self.write_statement('nvl clear')

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
        self.write_statement('jump %s' % self.parser.skiplabel[skipto])

    def get_image(self, img, pos):
        if not (pos, img) in self.images:
            self.images[(pos, img)] = "__image__%i" % self.nimage
            self.nimage += 1

        return self.images[(pos, img)]

    def get_var(self, token):
        if token.type == "VARNUM":
            return '%s[%s]' % (self.vars['numvars'], token.escaped)
        elif token.type == "VARSTR":
            return '%s[%s]' % (self.vars['strvars'], token.escaped)
        else:
            return token.escaped

    def read_command(self, token):
        if token.value == 'autoclick':
            self.cmd_autoclick()
        elif token.value == 'bg':
            self.cmd_bg()
        elif token.value == 'br':
            self.cmd_br()
        elif token.value == 'cl':
            self.cmd_cl()
        elif token.value == 'csp':
            self.cmd_csp()
        elif token.value == 'goto':
            self.cmd_goto()
        elif token.value == 'gosub':
            self.cmd_gosub()
        elif token.value == 'if':
            self.cmd_if()
        elif token.value == 'inc':
            self.cmd_inc()
        elif token.value == 'ld':
            self.cmd_ld()
        elif token.value == 'lsp':
            self.cmd_lsp()
        elif token.value == 'mov':
            self.cmd_mov()
        elif token.value == 'msp':
            self.cmd_msp()
        elif token.value == 'numalias':
            self.cmd_numalias()
        elif token.value == 'play':
            self.cmd_play()
        elif token.value == 'playstop':
            self.cmd_playstop()
        elif token.value == 'print':
            self.cmd_print()
        elif token.value == 'quakex':
            self.cmd_quakex()
        elif token.value == 'quakey':
            self.cmd_quakey()
        elif token.value == 'repaint':
            self.cmd_repaint()
        elif token.value == 'resettimer':
            self.cmd_resettimer()
        elif token.value == 'return':
            self.cmd_return()
        elif token.value == 'select':
            self.cmd_select()
        elif token.value == 'selgosub':
            self.cmd_selgosub()
        elif token.value == 'setcursor':
            self.cmd_setcursor()
        elif token.value == 'setwindow':
            self.cmd_setwindow()
        elif token.value == 'stop':
            self.cmd_stop()
        elif token.value == 'stralias':
            self.cmd_stralias()
        elif token.value == 'textoff':
            self.cmd_textoff()
        elif token.value == 'texton':
            self.cmd_texton()
        elif token.value == '!w':
            self.cmd_w()
        elif token.value == 'wait':
            self.cmd_wait()
        elif token.value == 'waittimer':
            self.cmd_waittimer()
        elif token.value == 'wave':
            self.cmd_wave()
        elif token.value == 'waveloop':
            self.cmd_waveloop()
        elif token.value == 'wavestop':
            self.cmd_wavestop()
        elif token.value == 'windoweffect':
            self.cmd_windoweffect()
        else:
            sys.stderr.write('Unknown command: %s\n' % token.value)

    def cmd_autoclick(self):
        # NUM
        autoclick = self.parser.read("NUM").value
        if autoclick == '0':
            autoclick = '3600000'
        self.write_statement('$ %s=%s/1000' % (self.vars['autoclick'], autoclick))

    def cmd_bg(self):
        bg = self.parser.read(["STR", "COLOR", "VARSTR"])
        self.parser.read("COMMA")
        effect = self.parser.read(["NUM", "VARNUM"])

        img = self.get_image(bg, 'bg')
        self.write_statement('scene bg %s' % img)

    def cmd_br(self):
        self.write_statement('".{fast}{nw}"')

    def cmd_cl(self):
        # IDENTIFIER,NUM
        pos = self.parser.read("IDENTIFIER").value
        self.parser.read("COMMA")
        effect = self.parser.read(["NUM", "VARNUM"])

        if pos == 'a':
            self.write_statement('hide r')
            self.write_statement('hide c')
            self.write_statement('hide l')
        else:
            self.write_statement('hide %s' % pos)

    def cmd_csp(self):
        # NUM
        id = self.parser.read("NUM").value
        if id == '-1':
            self.write_statement('$ for img in %s.keys(): renpy.hide(img)' % self.vars['sprites'])
        else:
            self.write_statement('hide s%s' % id)

    def cmd_gosub(self):
        # LABEL
        label = self.parser.read("LABEL").value
        self.write_statement('call %s' % label.replace('*', ''))

    def cmd_goto(self):
        # LABEL
        label = self.parser.read("LABEL").value
        self.write_statement('jump %s' % label.replace('*', ''))

    def cmd_if(self):
        stmt = 'if'
        while True:
            op = self.parser.read(["NUM", "VARNUM", "LT", "LE", "GT", "GE", "EQ", "NEQ", "AND", "OR"], mandatory=False)

            if op is None:
                break

            stmt += ' '
            if op.type == "VARNUM":
                stmt += self.get_var(op)
            else:
                stmt += op.escaped

        self.write_statement("%s:" % stmt)
        self.indent += 1
        token = self.parser.read()
        self.handle_token(token)
        self.indent -= 1

    def cmd_inc(self):
        # VARNUM
        var = self.parser.read("VARNUM")
        self.write_statement('$ %s+=1' % self.get_var(var))

    def cmd_ld(self):
        # IDENTIFIER,STR,NUM
        pos = self.parser.read("IDENTIFIER").value
        self.parser.read("COMMA")
        sprite = self.parser.read(["STR", "VARSTR"])
        self.parser.read("COMMA")
        effect = self.parser.read(["NUM", "VARNUM"])

        img = self.get_image(sprite, pos)

        self.write_statement('$ %s=get_xpos("%s", "%s")' % (self.vars['xpos'], img, pos))
        self.write_statement('show %s %s at Position(xanchor=0, yalign=1.0, xpos=%s)' % (pos, img, self.vars['xpos']))

    def cmd_lsp(self):
        # NUM,STR,NUM,NUM,NUM
        id = self.parser.read("NUM").value
        self.parser.read("COMMA")
        sprite = self.parser.read(["STR", "VARSTR"])
        self.parser.read("COMMA")
        xpos = self.parser.read(["NUM"])
        self.parser.read("COMMA")
        ypos = self.parser.read(["NUM"])
        if self.parser.read("COMMA", mandatory=False) is not None:
            alpha = self.parser.read(["NUM"]).value
        else:
            alpha = '0'

        img = self.get_image(sprite, "s%s" % id)

        self.write_statement('$ %s["s%s"] = "%s"' % (self.vars['sprites'], id, img))
        self.write_statement('$ %s=int(%s*%s)' % (self.vars['xpos'], xpos.value, self.vars['rw']))
        self.write_statement('$ %s=int(%s*%s)' % (self.vars['ypos'], ypos.value, self.vars['rh']))
        self.write_statement('$ %s = Position(xanchor=0, yanchor=0, xpos=%s, ypos=%s)' % (self.vars['spos'], self.vars['xpos'], self.vars['ypos']))
        self.write_statement('$ %s=%s' % (self.vars['salpha'], alpha))
        self.write_statement('$ %s = Transform(alpha=%s/255.0)' % (self.vars['salphatrans'], self.vars['salpha']))
        self.write_statement('$ renpy.show(("s%s", %s["s%s"]), at_list=[%s, %s])' % (id, self.vars['sprites'], id, self.vars['spos'], self.vars['salphatrans']))

    def cmd_mov(self):
        var = self.parser.read(["VARNUM", "VARSTR"])
        self.parser.read("COMMA")

        if var.type == "VARNUM":
            val = self.parser.read(["NUM", "VARNUM"])
        else:
            val = self.parser.read(["STR", "VARSTR"])

        if not var in self.variables:
            self.variables[var] = []
        self.variables[var].append(val)

        self.write_statement('$ %s=%s' % (self.get_var(var), self.get_var(val))) 

    def cmd_msp(self):
        # NUM,NUM,NUM,NUM
        id = self.parser.read("NUM").value
        self.parser.read("COMMA")
        xpos = self.parser.read(["NUM"])
        self.parser.read("COMMA")
        ypos = self.parser.read(["NUM"])
        if self.parser.read("COMMA", mandatory=False) is not None:
            alpha = self.parser.read(["NUM"]).value
        else:
            alpha = '0'

        self.write_statement('$ %s+=%s' % (self.vars['xpos'], xpos.value))
        self.write_statement('$ %s+=%s' % (self.vars['ypos'], ypos.value))
        self.write_statement('$ %s = Position(xanchor=0, yanchor=0, xpos=%s, ypos=%s)' % (self.vars['spos'], self.vars['xpos'], self.vars['ypos']))
        self.write_statement('$ %s+=%s' % (self.vars['salpha'], alpha))
        self.write_statement('$ %s = Transform(alpha=%s/255.0)' % (self.vars['salphatrans'], self.vars['salpha']))
        self.write_statement('$ renpy.hide("s%s")' % id)
        self.write_statement('$ renpy.show(("s%s", %s["s%s"]), at_list=[%s, %s])' % (id, self.vars['sprites'], id, self.vars['spos'], self.vars['salphatrans']))

    def cmd_numalias(self):
        # IDENTIFIER,NUM
        alias = self.parser.read("IDENTIFIER").value
        self.parser.read("COMMA")
        val = self.parser.read("NUM").value
        
        self.parser.numaliases[alias] = val
        self.write_statement('$ ns_na_%s = %s' % (alias, val))
        
    def cmd_play(self):
        # STR
        track = self.parser.read("STR").value.replace('*', '').replace('"', '')

        if len(track) == 1:
            track = '0' + track

        self.write_statement('play music "CD/track%s.ogg"' % track)

    def cmd_playstop(self):
        self.write_statement('stop music')

    def cmd_print(self):
        # NUM
        effect = self.parser.read("NUM", "VARNUM")

    def cmd_quakex(self):
        # NUM, NUM
        amp = self.parser.read("NUM")
        self.parser.read("COMMA")
        dur = self.parser.read("NUM")

        self.write_statement('with hpunch')

    def cmd_quakey(self):
        # NUM, NUM
        amp = self.parser.read("NUM")
        self.parser.read("COMMA")
        dur = self.parser.read("NUM")

        self.write_statement('with vpunch')

    def cmd_repaint(self):
        pass

    def cmd_resettimer(self):
        pass

    def cmd_return(self):
        self.write_statement('return')

    def cmd_select(self):
        self.write_statement('menu:')
        while True:
            text = self.parser.read("TEXT")
            self.parser.read("COMMA")
            label = self.parser.read("LABEL")

            text = text.value.replace('`', '')
            text = self.escape_text(text)
            self.write_statement('  "%s":' % text)
            self.write_statement('    jump %s' % label.value.replace('*', ''))

            if self.parser.read("COMMA", mandatory=False) is None:
                break

    def cmd_selgosub(self):
        self.write_statement('menu:')
        while True:
            text = self.parser.read("TEXT")
            self.parser.read("COMMA")
            label = self.parser.read("LABEL")

            text = text.value.replace('`', '')
            text = self.escape_text(text)
            self.write_statement('  "%s":' % text)
            self.write_statement('    call %s' % label.value.replace('*', ''))

            if self.parser.read("COMMA", mandatory=False) is None:
                break

    def cmd_setcursor(self):
        # NUM,STR,NUM,NUM
        self.parser.read("NUM")
        self.parser.read("COMMA")
        self.parser.read("STR")
        self.parser.read("COMMA")
        self.parser.read("NUM")
        self.parser.read("COMMA")
        self.parser.read("NUM")

    def cmd_setwindow(self):
        # NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,COLOR,NUM,NUM,NUM,NUM
        # NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,NUM,STR,NUM,NUM
        for i in range(11):
            self.parser.read("NUM")
            self.parser.read("COMMA")

        bg = self.parser.read(["STR", "COLOR"])

        img = self.get_image(bg, 'bg')
        self.write_statement('scene bg %s' % img)

        if bg.type == "STR":
            r = 2
        else:
            r = 4

        for i in range(r):
            self.parser.read("COMMA")
            self.parser.read("NUM")

    def cmd_stop(self):
        self.write_statement('stop music')
        self.write_statement('stop sound')

    def cmd_stralias(self):
        # IDENTIFIER,STR
        alias = self.parser.read("IDENTIFIER").value
        self.parser.read("COMMA")
        val = self.parser.read("STR").value

        self.parser.straliases[alias] = val
        self.write_statement('$ ns_sa_%s = %s' % (alias, val))

    def cmd_textoff(self):
        self.write_statement('window hide')

    def cmd_texton(self):
        self.write_statement('window show')

    def cmd_w(self):
        # NUM
        wait = self.parser.read("NUM")
        self.write_statement('$ renpy.pause(%s/1000.0)' % wait.value)

    def cmd_wait(self):
        # NUM
        wait = self.parser.read("NUM")
        self.write_statement('$ renpy.pause(%s/1000.0)' % wait.value)


    def cmd_waittimer(self):
        # NUM
        timer = self.parser.read(["NUM", "VARNUM"])
        self.write_statement('$ renpy.pause(%s/1000.0)' % self.get_var(timer))

    def cmd_wave(self):
        # STR
        track = self.parser.read(["STR", "IDENTIFIER", "VARSTR"])
        self.write_statement('play sound %s' % self.get_var(track).lower())

    def cmd_waveloop(self):
        # STR
        track = self.parser.read(["STR", "IDENTIFIER", "VARSTR"])
        self.write_statement('play sound %s loop' % self.get_var(track))

    def cmd_wavestop(self):
        self.write_statement('stop sound')

    def cmd_windoweffect(self):
        # NUM[,NUM[,STR]]
        self.parser.read("NUM")
        comma = self.parser.read("COMMA", mandatory=False)
        if comma is not None:
            self.parser.read("NUM")
            comma = self.parser.read("COMMA", mandatory=False)
            if comma is not None:
                self.parser.read("STR")

if __name__ == '__main__':
    parser = Parser()
    input = open(sys.argv[1], 'r', encoding='sjis')

    parser.tokenize(input.read())

    input.close()

    translator = Translator(parser, sys.stdout)

    translator.translate()

