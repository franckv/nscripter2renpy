init 1:
  transform right2:
    xalign 1.33

  transform left2:
    xalign -0.03

  python:
    menu = nvl_menu
    narrator = Character(None, kind=nvl)
    autoclick = 3600
    rw = None
    rh = None
    widhto = None
    heigho = None
    sprites = {}
    images_size = {}

    def scale(img):
      global rw, rh
      if rw is None:
          (w, h) = Image(img).load().get_size()
          rw = config.screen_width / float(w)
          rh = config.screen_height / float(h)
      return im.FactorScale(img, rw, rh)
  
    def alpha_blend(img, id):
      global rw, rh, images_size
      (w, h) = Image(img).load().get_size()
      images_size[id] = (w, h)
      i = im.Crop(img, (0, 0, w/2, h))
      m = im.MatrixColor(im.Crop(img, (w/2, 0, w/2, h)), im.matrix.invert())
      return im.FactorScale(im.AlphaMask(i, m), rw, rh)

    def get_xpos(id, pos):
      global rw, rh, images_size
      if pos == 'l':
        n = 1
      elif pos == 'c':
        n = 2
      elif pos =='r':
        n = 3

      (w, h) = images_size[id]
      xpos = int(config.screen_width * n / 4 - w *rw / 4)

      return xpos
