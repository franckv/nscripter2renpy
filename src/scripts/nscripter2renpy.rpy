init 1:
  transform right2:
    xalign 1.33

  transform left2:
    xalign -0.03

  python:
    menu = nvl_menu
    narrator = Character(None, kind=nvl)
    ns_autoclick = 3600
    ns_rw = None
    ns_rh = None
    ns_sprites = {}
    ns_images_size = {}
    ns_numvars = [0,] * 4096
    ns_strvars = ["",] * 4096

    def scale(img):
      global ns_rw, ns_rh
      if ns_rw is None:
          (w, h) = Image(img).load().get_size()
          ns_rw = config.screen_width / float(w)
          ns_rh = config.screen_height / float(h)
      return im.FactorScale(img, ns_rw, ns_rh)
  
    def alpha_blend(img, id):
      global ns_rw, ns_rh, ns_images_size
      (w, h) = Image(img).load().get_size()
      ns_images_size[id] = (w, h)
      i = im.Crop(img, (0, 0, w/2, h))
      m = im.MatrixColor(im.Crop(img, (w/2, 0, w/2, h)), im.matrix.invert())
      return im.FactorScale(im.AlphaMask(i, m), ns_rw, ns_rh)

    def get_xpos(id, pos):
      global ns_rw, ns_rh, ns_images_size
      if pos == 'l':
        n = 1
      elif pos == 'c':
        n = 2
      elif pos =='r':
        n = 3

      (w, h) = ns_images_size[id]
      xpos = int(config.screen_width * n / 4 - w * ns_rw / 4)

      return xpos
