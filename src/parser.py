import os, sys

import Image

from lexer import Lexer, Token

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
            ("VARSTR", r"\$\%?\w*"),
            ("LABEL", r"\*\w*"),
            ("SKIP", (r"skip\s*-?[0-9]+", self.skip_cb)),
            ("COLOR", r"#[a-fA-F0-9]{6}|white|black"),
            ("IDENTIFIER", r"[a-zA-Z_]\w*|!w|!sd|!s|!d"),
            ("STR", r"\"[^\"\n]*\"+"),
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

    def read_script(self, file, encrypted = True):
        content = file.read()
        result = ''
        if encrypted:
            for c in content:
                val = ord(c)
                val ^= 0x84
                result += chr(val)
        else:
            result = content

        return result

    def escape(self, token):
        if token.type == "STR":
            return token.value.replace('\\', '/')
        elif token.type == "IDENTIFIER":
            return token.value
        elif token.type == "NUMALIAS":
            return self.numaliases[token.value]
        elif token.type == "STRALIAS":
            return self.straliases[token.value]
        elif token.type == "VARNUM":
            var = token.value.replace('%', '')
            if var in self.numaliases:
                val = self.numaliases[var]
            else:
                val = var
            return 'ns_state.numvars[%s]' % val
        elif token.type == "VARSTR":
            var = token.value.replace('$', '')
            if var in self.numaliases:
                val = self.numaliases[var]
            else:
                val = var
            return 'ns_state.strvars[%s]' % val
        elif token.type == "COLOR":
            return '"%s"' % token.value
        elif token.type == 'AND':
            return 'and'
        elif token.type == 'OR':
            return 'or'
        else:
            return token.value

    def peek(self):
        return self.tokens[self.current]

    def read(self, expectedType=None, mandatory=True):
        if self.current >= len(self.tokens):
            return None

        token = self.tokens[self.current]
        if token.type == 'IDENTIFIER':
            if token.value in self.numaliases:
                token.type = 'NUMALIAS'
            elif token.value in self.straliases:
                token.type = 'STRALIAS'

        if expectedType is None or (type(expectedType).__name__=='list' and token.type in expectedType) or token.type == expectedType:
            self.current += 1
            token.escaped = self.escape(token)
            return token
        else:
            if mandatory:
                raise SyntaxError("Expected %s on %i got %s (%s)" % (expectedType, token.line, token.type, token.value))
            else:
                return None

class Translator(object):
    def __init__(self, parser, out):
        self.parser = parser
        self.out = out
        self.indent = 0
        self.skipline = 0

    def translate(self):
        skipdone = {}

        self.write_statement('label after_load:')
        self.indent += 1
        self.write_statement('$ init_vars(False)')
        self.write_statement('return\n')
        self.indent = 0

        self.write_statement('label start:')
        self.indent += 1
        self.write_statement('$ init_vars(True)')
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

        self.indent = 0

    def handle_token(self, token):
        if token.line == self.skipline:
            return

        if token.type == "IDENTIFIER":
            self.read_command(token)
        elif token.type == "LABEL":
            self.indent = 0
            self.write_statement('\nlabel %s:' % token.value.replace('*', ''))
            self.indent = 1
        elif token.type == "TEXT":
            self.read_text(token)
        elif token.type == "COLOR":
            self.write_statement('# set color : %s' % token.value)
        elif token.type == "SKIP":
            self.read_skip(token)
        elif token.type == "SEP":
            pass
        elif token.type == "PLUS":
            pass
        else:
            sys.stderr.write('Invalid token: %s (%s) at %d\n' % (token.type, token.value, token.line))
            self.skipline = token.line

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
        text = text.replace('@', '{w}')
        text = text.replace('\\', '{w}')
        text = text.replace('{w}{nw}', '')
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

    def read_command(self, token):
        if token.value == 'add':
            self.cmd_add()
        elif token.value == 'autoclick':
            self.cmd_autoclick()
        elif token.value == 'bg':
            self.cmd_bg()
        elif token.value == 'br':
            self.cmd_br()
        elif token.value == 'btn':
            self.cmd_btn()
        elif token.value == 'btndef':
            self.cmd_btndef()
        elif token.value == 'btnwait':
            self.cmd_btnwait()
        elif token.value == 'caption':
            self.cmd_caption()
        elif token.value == 'cl':
            self.cmd_cl()
        elif token.value == 'click':
            self.cmd_click()
        elif token.value == 'clickstr':
            self.cmd_clickstr()
        elif token.value == 'cmp':
            self.cmd_cmp()
        elif token.value == 'csp':
            self.cmd_csp()
        elif token.value == '!d':
            self.cmd_d()
        elif token.value == 'date':
            self.cmd_date()
        elif token.value == 'dec':
            self.cmd_dec()
        elif token.value == 'delay':
            self.cmd_delay()
        elif token.value == 'effect':
            self.cmd_effect()
        elif token.value == 'effectblank':
            self.cmd_effectblank()
        elif token.value == 'end':
            self.cmd_end()
        elif token.value == 'filelog':
            self.cmd_filelog()
        elif token.value == 'game':
            self.cmd_game()
        elif token.value == 'globalon':
            self.cmd_globalon()
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
        elif token.value == 'lookbackbutton':
            self.cmd_lookbackbutton()
        elif token.value == 'lookbackcolor':
            self.cmd_lookbackcolor()
        elif token.value == 'lsp':
            self.cmd_lsp()
        elif token.value == 'menuselectcolor':
            self.cmd_menuselectcolor()
        elif token.value == 'menusetwindow':
            self.cmd_menusetwindow()
        elif token.value == 'monocro':
            self.cmd_monocro()
        elif token.value == 'mov':
            self.cmd_mov()
        elif token.value == 'msp':
            self.cmd_msp()
        elif token.value == 'notif':
            self.cmd_notif()
        elif token.value == 'nsa':
            self.cmd_nsa()
        elif token.value == 'nsadir':
            self.cmd_nsadir()
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
        elif token.value == 'rmenu':
            self.cmd_rmenu()
        elif token.value == '!s':
            self.cmd_s()
        elif token.value == 'savename':
            self.cmd_savename()
        elif token.value == 'savenumber':
            self.cmd_savenumber()
        elif token.value == '!sd':
            self.cmd_sd()
        elif token.value == 'select':
            self.cmd_select()
        elif token.value == 'selectcolor':
            self.cmd_selectcolor()
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
        elif token.value == 'sub':
            self.cmd_sub()
        elif token.value == 'systemcall':
            self.cmd_systemcall()
        elif token.value == 'textclear':
            self.cmd_textclear()
        elif token.value == 'textoff':
            self.cmd_textoff()
        elif token.value == 'texton':
            self.cmd_texton()
        elif token.value == 'trap':
            self.cmd_trap()
        elif token.value == 'versionstr':
            self.cmd_versionstr()
        elif token.value == 'vsp':
            self.cmd_vsp()
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

    def cmd_add(self):
        # VARNUM, NUM
        # VARSTR, STR
        var = self.parser.read(["VARNUM", "VARSTR"])
        self.parser.read("COMMA")

        if var.type == "VARNUM":
            val = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])
        else:
            val = self.parser.read(["STR", "VARSTR", "STRALIAS"])

        self.write_statement('$ %s+=%s' % (var.escaped, val.escaped)) 

    def cmd_autoclick(self):
        # NUM
        autoclick = self.parser.read("NUM").value

    def cmd_bg(self):
        bg = self.parser.read(["STR", "COLOR", "VARSTR", "STRALIAS"])
        comma = self.parser.read("COMMA", mandatory=False)
        if comma is not None:
            effect = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])

        self.write_statement('$ renpy.scene()')
        self.write_statement('$ show_image(ns_state, %s, "bg")' % bg.escaped)

    def cmd_br(self):
        self.write_statement('"{fast}{nw}"')

    def cmd_btn(self):
        # NUM,NUM,NUM,NUM,NUM,NUM,NUM
        self.parser.read("NUM")
        self.parser.read("COMMA")
        self.parser.read("NUM")
        self.parser.read("COMMA")
        self.parser.read("NUM")
        self.parser.read("COMMA")
        self.parser.read("NUM")
        self.parser.read("COMMA")
        self.parser.read("NUM")
        self.parser.read("COMMA")
        self.parser.read("NUM")
        self.parser.read("COMMA")
        self.parser.read("NUM")

    def cmd_btndef(self):
        filename = self.parser.read(['STR', 'VARSTR', 'STRALIAS', 'IDENTIFIER'])

    def cmd_btnwait(self):
        var = self.parser.read("VARNUM")
        val = Token('NUM', 0, 0)
        self.write_statement('$ %s=%s' % (var.escaped, val.escaped)) 

    def cmd_caption(self):
        caption = self.parser.read(['STR', 'STRALIAS', 'VARSTR'])

    def cmd_cl(self):
        # IDENTIFIER,NUM
        pos = self.parser.read("IDENTIFIER").value
        self.parser.read("COMMA")
        effect = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])

        if pos == 'a':
            self.write_statement('$ renpy.hide("r")')
            self.write_statement('$ renpy.hide("c")')
            self.write_statement('$ renpy.hide("l")')
        else:
            self.write_statement('$ renpy.hide("%s")' % pos)

    def cmd_click(self):
        self.write_statement('$ renpy.pause()')

    def cmd_clickstr(self):
        self.parser.read(['STR', 'STRALIAS', 'VARSTR', 'TEXT'])
        while (self.parser.read('COMMA', mandatory=False) is not None):
            s = self.parser.read(['STR', 'STRALIAS', 'VARSTR', 'TEXT'], mandatory=False)
            if s is None:
                break
        self.parser.read(["NUM", "VARNUM", "NUMALIAS"])


    def cmd_cmp(self):
        # VARNUM, STR, STR
        var = self.parser.read('VARNUM')
        self.parser.read('COMMA')
        str1 = self.parser.read(['STR', 'STRALIAS', 'VARSTR'])
        self.parser.read('COMMA')
        str2 = self.parser.read(['STR', 'STRALIAS', 'VARSTR'])

        self.write_statement('$ %s=cmp(%s, %s)' % (var.escaped, str1.escaped, str2.escaped))

    def cmd_csp(self):
        # NUM
        id = self.parser.read("NUM").value
        if id == '-1':
            self.write_statement('$ for img in ns_state.sprites: renpy.hide(img)')
        else:
            self.write_statement('hide s%s' % id)

    def cmd_d(self):
        # NUM
        wait = self.parser.read(["NUM", "NUMALIAS"])
        self.write_statement('$ renpy.pause(%s/1000.0)' % wait.value)

    def cmd_date(self):
        year = self.parser.read("VARNUM")
        self.parser.read('COMMA')
        month = self.parser.read("VARNUM")
        self.parser.read('COMMA')
        day = self.parser.read("VARNUM")

    def cmd_dec(self):
        # VARNUM
        var = self.parser.read("VARNUM")
        self.write_statement('$ %s-=1' % var.escaped)

    def cmd_delay(self):
        # NUM
        wait = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])
        self.write_statement('$ renpy.pause(%s/1000.0)' % wait.value)

    def cmd_effect(self):
        # NUM,NUM[,NUM[,STR]]
        effect_id = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])
        self.parser.read("COMMA")
        effect_type = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])
        comma = self.parser.read("COMMA", mandatory=False)
        if comma is not None:
            duration = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])
            comma = self.parser.read("COMMA", mandatory=False)
            if comma is not None:
                filename = self.parser.read(['STR', 'STRALIAS', 'VARSTR'])
            else:
                filename = None
        else:
            duration = 0
            filename = None

    def cmd_effectblank(self):
        self.parser.read(["NUM", "VARNUM", "NUMALIAS"])

    def cmd_end(self):
        self.write_statement('$ renpy.full_restart()')

    def cmd_filelog(self):
        pass

    def cmd_game(self):
        pass

    def cmd_globalon(self):
        pass

    def cmd_gosub(self):
        # LABEL
        label = self.parser.read("LABEL").value
        self.write_statement('call %s' % label.replace('*', ''))

    def cmd_goto(self):
        # LABEL
        label = self.parser.read("LABEL").value
        self.write_statement('jump %s' % label.replace('*', ''))

    def cmd_if(self, notif=False):
        stmt = 'if'
        while True:
            if self.parser.peek().value == 'fchk':
                self.parser.read("IDENTIFIER")
                filename = self.parser.read(['STR', 'VARSTR', 'STRALIAS', 'IDENTIFIER'])
                stmt += ' 0 ==1'
            else:
                op = self.parser.read(["NUM", "VARNUM", "NUMALIAS", "LT", "LE", "GT", "GE", "EQ", "NEQ", "AND", "OR"], mandatory=False)

                if op is None:
                    break
                else:
                    stmt += ' ' + op.escaped

        if notif:
            self.write_statement("not (%s):" % stmt)
        else:
            self.write_statement("%s:" % stmt)
        self.indent += 1

        while True:
            token = self.parser.read()
            self.handle_token(token)
            sep = self.parser.read('SEP', mandatory=False)
            if sep is None:
                break
        self.indent -= 1

    def cmd_inc(self):
        # VARNUM
        var = self.parser.read("VARNUM")
        self.write_statement('$ %s+=1' % var.escaped)

    def cmd_ld(self):
        # IDENTIFIER,STR,NUM
        pos = self.parser.read("IDENTIFIER")
        self.parser.read("COMMA")
        sprite = self.parser.read(["STR", "VARSTR", "STRALIAS"])
        self.parser.read("COMMA")
        effect = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])

        self.write_statement('$ show_standing(ns_state, %s, "%s")' % (sprite.escaped, pos.escaped))

    def cmd_lookbackbutton(self):
        self.parser.read(["STR", "VARSTR", "STRALIAS"])
        self.parser.read("COMMA")
        self.parser.read(["STR", "VARSTR", "STRALIAS"])
        self.parser.read("COMMA")
        self.parser.read(["STR", "VARSTR", "STRALIAS"])
        self.parser.read("COMMA")
        self.parser.read(["STR", "VARSTR", "STRALIAS"])

    def cmd_lookbackcolor(self):
        col = self.parser.read('COLOR')

    def cmd_lsp(self):
        # NUM,STR,NUM,NUM,NUM
        id = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])
        self.parser.read("COMMA")
        sprite = self.parser.read(["STR", "VARSTR", "STRALIAS"])
        self.parser.read("COMMA")
        xpos = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])
        self.parser.read("COMMA")
        ypos = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])
        if self.parser.read("COMMA", mandatory=False) is not None:
            alpha = self.parser.read(["NUM"]).value
        else:
            alpha = '0'

        self.write_statement('$ store_show_sprite(ns_state, %s, %s, %s, %s, %s)' % (sprite.escaped, id.escaped, xpos.escaped, ypos.escaped, alpha))

    def cmd_menuselectcolor(self):
        self.parser.read("COLOR")
        self.parser.read("COMMA")
        self.parser.read("COLOR")
        self.parser.read("COMMA")
        self.parser.read("COLOR")

    def cmd_menusetwindow(self):
        # NUM,NUM,NUM,NUM,NUM,NUM,COLOR
        for i in range(6):
            self.parser.read("NUM")
            self.parser.read("COMMA", mandatory=False)

        bg = self.parser.read(["STR", "COLOR"])

    def cmd_monocro(self):
        col = self.parser.read(['COLOR', 'IDENTIFIER'])

    def cmd_mov(self):
        var = self.parser.read(["VARNUM", "VARSTR"])
        self.parser.read("COMMA")

        if var.type == "VARNUM":
            val = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])
        else:
            val = self.parser.read(["STR", "VARSTR", "STRALIAS"])

        self.write_statement('$ %s=%s' % (var.escaped, val.escaped)) 

    def cmd_msp(self):
        # NUM,NUM,NUM,NUM
        id = self.parser.read("NUM")
        self.parser.read("COMMA")
        xpos = self.parser.read(["NUM"])
        self.parser.read("COMMA")
        ypos = self.parser.read(["NUM"])
        if self.parser.read("COMMA", mandatory=False) is not None:
            alpha = self.parser.read(["NUM"]).value
        else:
            alpha = '0'

        self.write_statement('$ move_sprite(ns_state, %s, %s, %s, %s)' % (id.escaped, xpos.escaped, ypos.escaped, alpha))

    def cmd_notif(self):
        return self.cmd_if(notif=True)

    def cmd_nsa(self):
        pass

    def cmd_nsadir(self):
        # STR
        dir = self.parser.read("STR").value

    def cmd_numalias(self):
        # IDENTIFIER,NUM
        alias = self.parser.read("IDENTIFIER").value
        self.parser.read("COMMA")
        val = self.parser.read("NUM").value
        
        self.parser.numaliases[alias] = val
        self.write_statement('# %s = %s' % (alias, val))
        
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
        effect = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])

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

    def cmd_rmenu(self):
        while True:
            text = self.parser.read("TEXT")
            self.parser.read("COMMA")
            label = self.parser.read("IDENTIFIER")

            if self.parser.read("COMMA", mandatory=False) is None:
                break

    def cmd_s(self):
        speed = self.parser.read(["NUM", "NUMALIAS"])

    def cmd_savename(self):
        self.parser.read(["STR", "STRALIAS", "VARSTR", "TEXT"])
        self.parser.read("COMMA")
        self.parser.read(["STR", "STRALIAS", "VARSTR", "TEXT"])
        self.parser.read("COMMA")
        self.parser.read(["STR", "STRALIAS", "VARSTR", "TEXT"])

    def cmd_savenumber(self):
        self.parser.read(["NUM", "VARNUM", "NUMALIAS"])

    def cmd_sd(self):
        pass

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

    def cmd_selectcolor(self):
        self.parser.read("COLOR")
        self.parser.read("COMMA")
        self.parser.read("COLOR")

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
            self.parser.read("COMMA", mandatory=False)

        bg = self.parser.read(["STR", "COLOR"])

        self.write_statement('$ renpy.scene()')
        self.write_statement('$ show_image(ns_state, %s, "bg")' % bg.escaped)

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
        val = self.parser.read("STR").escaped

        self.parser.straliases[alias] = val
        self.write_statement('# %s = %s' % (alias, val))

    def cmd_sub(self):
        # VARNUM, NUM
        # VARSTR, STR
        var = self.parser.read("VARNUM")
        self.parser.read("COMMA")
        val = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])

        self.write_statement('$ %s-=%s' % (var.escaped, val.escaped)) 

    def cmd_systemcall(self):
        command = self.parser.read("IDENTIFIER").value

    def cmd_textclear(self):
        self.write_statement('nvl clear')

    def cmd_textoff(self):
        self.write_statement('window hide')

    def cmd_texton(self):
        self.write_statement('window show')

    def cmd_trap(self):
        alias = self.parser.read(["IDENTIFIER", "LABEL"])

    def cmd_versionstr(self):
        # STR, STR
        v1 = self.parser.read("STR")
        self.parser.read("COMMA")
        self.parser.read("STR")

    def cmd_vsp(self):
        # NUM,NUM
        id = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])
        self.parser.read("COMMA")
        visibility = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])

        self.write_statement('$ toggle_sprite(ns_state, %s, %s)' % (id.escaped, visibility.escaped))

    def cmd_w(self):
        # NUM
        wait = self.parser.read(["NUM", "NUMALIAS"])
        self.write_statement('$ renpy.pause(%s/1000.0)' % wait.value)

    def cmd_wait(self):
        # NUM
        wait = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])
        self.write_statement('$ renpy.pause(%s/1000.0)' % wait.value)

    def cmd_waittimer(self):
        # NUM
        timer = self.parser.read(["NUM", "VARNUM", "NUMALIAS"])
        self.write_statement('$ renpy.pause(%s/1000.0)' % timer.escaped)

    def cmd_wave(self):
        # STR
        track = self.parser.read(["STR", "STRALIAS", "VARSTR"])
        self.write_statement('play sound %s' % track.escaped.lower())

    def cmd_waveloop(self):
        # STR
        track = self.parser.read(["STR", "STRALIAS", "VARSTR"])
        self.write_statement('play sound %s loop' % track.escaped)

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

