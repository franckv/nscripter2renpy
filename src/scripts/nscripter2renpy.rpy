init 1:
  transform right2:
    xalign 1.33

  transform left2:
    xalign -0.03

  python:
    menu = nvl_menu
    narrator = Character(None, kind=nvl)
    class State:
        def __init__(self):
            self.rw = None
            self.rh = None
            self.sprites = {}
            self.numaliases = {}
            self.straliases = {}
            self.images_size = {}
            self.numvars = [0,] * 4096
            self.strvars = ["",] * 4096
            self.salpha = 0
            self.salphatrans = None
            self.spos = None
            self.ypos = 0
            self.xpos = 0

    ns_state_init = State()

    if persistent.initruns is None:
        persistent.initruns = 1
    print('init executed %d times' % persistent.initruns)
    persistent.initruns += 1

    def scale(state, img):
      if state.rw is None:
          (w, h) = Image(img).load().get_size()
          state.rw = config.screen_width / float(w)
          state.rh = config.screen_height / float(h)
      return im.FactorScale(img, state.rw, state.rh)
  
    def alpha_blend(state, img, id):
      (w, h) = Image(img).load().get_size()
      state.images_size[id] = (w, h)
      i = im.Crop(img, (0, 0, w/2, h))
      m = im.MatrixColor(im.Crop(img, (w/2, 0, w/2, h)), im.matrix.invert())
      return im.FactorScale(im.AlphaMask(i, m), state.rw, state.rh)

    def get_xpos(state, id, pos):
      if pos == 'l':
        n = 1
      elif pos == 'c':
        n = 2
      elif pos =='r':
        n = 3

      (w, h) = state.images_size[id]
      xpos = int(config.screen_width * n / 4 - w * state.rw / 4)

      return xpos

    def print_state(state):
      for var in state.__dict__:
        print(var, getattr(state, var))
      
    def init_vars(start):
      global ns_state, ns_state_init
      if not hasattr(renpy.store,'ns_state'):
        ns_state = {}
        for var in ns_state_init.__dict__:
          setattr(ns_state, var, getattr(ns_state_init, var))
