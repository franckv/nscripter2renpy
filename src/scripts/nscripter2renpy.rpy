init 1:
  transform right2:
    xalign 1.33

  transform left2:
    xalign -0.03

  python:
    menu = nvl_menu
    narrator = Character(None, kind=nvl)
    nimages = 1
    class State:
        def __init__(self):
            self.rw = None
            self.rh = None
            self.numaliases = {}
            self.straliases = {}
            self.numvars = [0,] * 4096
            self.strvars = ["",] * 4096
            self.sprites = [("", 0, 0, 0),] * 999
            self.images = {}
            self.images_size = {}
            self.salpha = 0
            self.salphatrans = None
            self.spos = None
            self.ypos = 0
            self.xpos = 0
            self.l = None
            self.c = None
            self.r = None

    ns_state_init = State()

    if persistent.initruns is None:
        persistent.initruns = 1
    print('init executed %d times' % persistent.initruns)
    persistent.initruns += 1

    def get_size(state, img):
      return Image(img).load().get_size()

    def scale(state, img):
      if state.rw is None:
          (w, h) = get_size(state, img)
          state.rw = config.screen_width / float(w)
          state.rh = config.screen_height / float(h)
      return im.FactorScale(img, state.rw, state.rh)
  
    def alpha_blend(state, img):
      (w, h) = get_size(state, img)
      i = im.Crop(img, (0, 0, w/2, h))
      m = im.MatrixColor(im.Crop(img, (w/2, 0, w/2, h)), im.matrix.invert())
      return im.FactorScale(im.AlphaMask(i, m), state.rw, state.rh)

    def show_image(state, filename, tag, at_list=[]):
      if filename.startswith("#"):
        img = renpy.store.Solid(filename)
      elif filename.startswith(":a;"):
        img = alpha_blend(state, filename.replace(":a;", "", 1))
      elif filename.startswith(":c;"):
        img = scale(state, filename.replace(":c;", "", 1))
      else:
        img = scale(state, filename)
      renpy.show(tag, at_list = at_list, what=img)

    def store_show_sprite(state, filename, id, xpos, ypos, alpha):
        state.sprites[id] = (filename, int(xpos * state.rw), int(ypos * state.rh), alpha)
        show_sprite(state, id)

    def toggle_sprite(state, id, visibility):
        if visibility == 0:
            renpy.hide("%s" % id)
        else:
            show_sprite(state, id)

    def show_sprite(state, id):
        (filename, xpos, ypos, alpha) = state.sprites[id]
        alphatrans = Transform(alpha=alpha/255.0)
        spos = Position(xanchor=0, yanchor=0, xpos=xpos, ypos=ypos)
        show_image(state, filename, "%s" % id, [alphatrans, spos])

    def move_sprite(state, id, dxpos, dypos, dalpha):
        (filename, xpos, ypos, alpha) = state.sprites[id]
        xpos += int(dxpos * state.rw)
        ypos += int(dypos * state.rh)
        alpha += dalpha
        state.sprites[id] = (filename, xpos, ypos, alpha)
        show_sprite(state, id)

    def show_standing(state, filename, pos):
      if pos == 'l':
        n = 1
      elif pos == 'c':
        n = 2
      elif pos =='r':
        n = 3

      (w, h) = get_size(state, filename.replace(":a;", "", 1).replace(":c;", "", 1))
      xpos = int(config.screen_width * n / 4 - w * state.rw / 4)

      spos = Position(xanchor=0, yalign=1.0, xpos=xpos)

      show_image(state, filename, pos, [spos])

    def print_state(state):
      for var in state.__dict__:
        print(var, getattr(state, var))
      
    def init_vars(start):
      global ns_state, ns_state_init
      if not hasattr(renpy.store,'ns_state'):
        ns_state = {}
        for var in ns_state_init.__dict__:
          setattr(ns_state, var, getattr(ns_state_init, var))
