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
            self.sprites = [0,] * 999
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

    def register_image(state, filename, alpha, size):
      img_id = "___image___%i" % nimages
      nimages += 1
      if filename.startswith('#'):
        renpy.image(img_id, filename)
      elif alpha:
        renpy.image(img_id, alpha_blend(state, filename, size))
      else:
        renpy.image(img_id, scale(state, filename, size))
      
      state.images[filename] = img_id
      state.images_size[img_id] = size

    def scale(state, img, size):
      if state.rw is None:
          (w, h) = size
          state.rw = config.screen_width / float(w)
          state.rh = config.screen_height / float(h)
      return im.FactorScale(img, state.rw, state.rh)
  
    def alpha_blend(state, img, size):
      (w, h) = size
      i = im.Crop(img, (0, 0, w/2, h))
      m = im.MatrixColor(im.Crop(img, (w/2, 0, w/2, h)), im.matrix.invert())
      return im.FactorScale(im.AlphaMask(i, m), state.rw, state.rh)

    def show_image(filename, at_list=[]):
      if filename in state.images:
        renpy.show(state.images[filename], at_list)

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
