# -*- coding: utf-8 -*-
#
#   Copyright (C) 2007-present Marc Culler, Nathan Dunfield and others.
#
#   This program is distributed under the terms of the
#   GNU General Public License, version 2 or later, as published by
#   the Free Software Foundation.  See the file gpl-2.0.txt for details.
#   The URL for this program is
#     http://www.math.uic.edu/~t3m/plink
#   A copy of the license file may be found at:
#     http://www.gnu.org/licenses/old-licenses/gpl-2.0.html
#
#   The development of this program was partially supported by
#   the National Science Foundation under grants DMS0608567,
#   DMS0504975 and DMS0204142.
"""
This module exports the class LinkEditor which is a full-featured
editing tool for link diagrams.
"""
import os, time, webbrowser, math

from .gui import *
from . import smooth
from .vertex import Vertex
from .arrow import Arrow
from .crossings import Crossing, ECrossing
from .colors import Palette
from .dialog import InfoDialog
from .manager import LinkManager
from .viewer import LinkViewer
from .version import version
from .ipython_tools import IPythonTkRoot

About = """This is version %s of PLink.

PLink draws piecewise linear link projections. It was
written in Python by Marc Culler and Nathan Dunfield with
support from the National Science Foundation. PLink is
distributed under the GNU General Public License.

Source code for Plink is available at:
    https://github.com/3-manifolds/PLink
Submit comments or bug reports at:
    https://github.com/3-manifolds/PLink/issues

To install PLink in your Python environment, run:
   pip install plink

PLink was inspired by SnapPea (written by Jeff Weeks) and
LinkSmith (written by Jim Hoste and Morwen Thistlethwaite).
""" % version

class PLinkBase(LinkViewer):
    """
    Base class for windows displaying a LinkViewer and an Info Window.
    FLAGET
    """
    def __init__(self, root=None, manifold=None, file_name=None, title='',
                 show_crossing_labels=False):
        self.initialize()
        self.show_crossing_labels=show_crossing_labels
        self.manifold = manifold
        self.title = title
        self.cursorx = 0
        self.cursory = 0
        self.colors = []
        self.color_keys = []
        # Window
        if root is None:
            # In IPython, this will remind the user to type %gui tk.
            self.window = root = IPythonTkRoot(className='plink')
        else:
            self.window = Tk_.Toplevel(root)
        self.window.protocol("WM_DELETE_WINDOW", self.done)
        if sys.platform == 'linux2' or sys.platform == 'linux':
            root.tk.call('namespace', 'import', '::tk::dialog::file::')
            root.tk.call('set', '::tk::dialog::file::showHiddenBtn',  '1')
            root.tk.call('set', '::tk::dialog::file::showHiddenVar',  '0')
        self.window.title(title)
        self.style = PLinkStyle()
        self.palette = Palette()
        # Frame and Canvas
        self.frame = ttk.Frame(self.window)
        self.canvas = Tk_.Canvas(self.frame,
                                 bg='#dcecff',
                                 width=500,
                                 height=500,
                                 borderwidth=0,
                                 highlightthickness=0)
        self.smoother = smooth.Smoother(self.canvas)
        self.infoframe = ttk.Frame(self.window)
        self.infotext_contents = Tk_.StringVar(self.window)
        self.infotext = ttk.Entry(self.infoframe,
                                  state='readonly',
                                  font='Helvetica 14',
                                  textvariable=self.infotext_contents)
        self.infoframe.pack(padx=0, pady=0, fill=Tk_.X, expand=Tk_.NO,
                            side=Tk_.BOTTOM)
        self.frame.pack(padx=0, pady=0, fill=Tk_.BOTH, expand=Tk_.YES)
        self.canvas.pack(padx=0, pady=0, fill=Tk_.BOTH, expand=Tk_.YES)
        self.infotext.pack(padx=5, pady=0, fill=Tk_.X, expand=Tk_.YES)
        self.show_DT_var = Tk_.IntVar(self.window)
        self.show_labels_var = Tk_.IntVar(self.window)
        self.info_var = Tk_.IntVar(self.window)
        self.style_var = Tk_.StringVar(self.window)
        self.style_var.set('pl')
        self.cursor_attached = False
        self.saved_crossing_data = None
        self.current_info = 0
        self.has_focus = True
        self.focus_after = None
        # Info window
        self.infotext.bind('<Control-Shift-C>',
                           lambda event : self.infotext.event_generate('<<Copy>>'))
        self.infotext.bind('<<Copy>>', self.copy_info)
        # Menus
        self._build_menus()
        # Key events
        self.window.bind('<Key>', self._key_press)
        self.window.bind('<KeyRelease>', self._key_release)
        # Go
        if file_name:
            self.load(file_name=file_name)

    def _key_release(self, event):
        """
        Handler for keyrelease events.
        """
        pass

    def _key_press(self, event):
        """
        Handler for keypress events.
        FLAGET
        """
        dx, dy = 0, 0
        key = event.keysym
        if key in ('plus', 'equal'):
            self.zoom_in()
        elif key in ('minus', 'underscore'):
            self.zoom_out()
        elif key == '0':
            self.zoom_to_fit()
        try:
            self._shift(*canvas_shifts[key])
        except KeyError:
            pass
        return

    def _build_menus(self):
        self.menubar = menubar = Tk_.Menu(self.window)
        self._add_file_menu()
        self._add_info_menu()
        self._add_tools_menu()
        self._add_style_menu()
        # self._add_reid_menu()
        self.window.config(menu=menubar)
        help_menu = Tk_.Menu(menubar, tearoff=0)
        help_menu.add_command(label='About PLink...', command=self.about)
        help_menu.add_command(label='Instructions ...', command=self.howto)
        menubar.add_cascade(label='Help', menu=help_menu)

    def _add_file_menu(self):
        file_menu = Tk_.Menu(self.menubar, tearoff=0)
        file_menu.add_command(label='Save ...', command=self.save)
        self.build_save_image_menu(self.menubar, file_menu)
        file_menu.add_separator()
        file_menu.add_command(label='Quit', command=self.done)
        self.menubar.add_cascade(label='File', menu=file_menu)

    def _add_info_menu(self):
        info_menu = Tk_.Menu(self.menubar, tearoff=0)
        info_menu.add_radiobutton(label='DT code', var=self.info_var,
                                  command=self.set_info, value=1)
        info_menu.add_radiobutton(label='Alphabetical DT', var=self.info_var,
                                  command=self.set_info, value=2)
        info_menu.add_radiobutton(label='Gauss code', var=self.info_var,
                                  command=self.set_info, value=3)
        info_menu.add_radiobutton(label='PD code', var=self.info_var,
                                  command=self.set_info, value=4)
        info_menu.add_radiobutton(label='BB framing', var=self.info_var,
                                  command=self.set_info, value=5)
        info_menu.add_separator()
        info_menu.add_checkbutton(label='DT labels', var=self.show_DT_var,
                                  command = self.update_info)
        if self.show_crossing_labels:
            info_menu.add_checkbutton(label='Crossing labels', var=self.show_labels_var,
                                      command = self.update_info)
        self.menubar.add_cascade(label='Info', menu=info_menu)

    # Override if you want a tools menu
    def _add_tools_menu(self):
        pass

    def _add_style_menu(self):
        style_menu = Tk_.Menu(self.menubar, tearoff=0)
        style_menu.add_radiobutton(label='PL', value='pl',
                              command=self.set_style,
                              variable=self.style_var)
        style_menu.add_radiobutton(label='Smooth',  value='smooth',
                              command=self.set_style,
                              variable=self.style_var)
        self._extend_style_menu(style_menu)
        self.menubar.add_cascade(label='Style', menu=style_menu)
        self._add_zoom_and_pan(style_menu)

    # Override to add additional style menu items
    def _extend_style_menu(self, style_menu):
        pass

    def _add_zoom_and_pan(self, style_menu):
        zoom_menu = Tk_.Menu(style_menu, tearoff=0)
        pan_menu = Tk_.Menu(style_menu, tearoff=0)
        # Accelerators are really slow on the Mac.  Bad UX
        if sys.platform == 'darwin':
            zoom_menu.add_command(label='Zoom in    \t+',
                                  command=self.zoom_in)
            zoom_menu.add_command(label='Zoom out   \t-',
                                  command=self.zoom_out)
            zoom_menu.add_command(label='Zoom to fit\t0',
                                  command=self.zoom_to_fit)
            pan_menu.add_command(label='Left  \t'+scut['Left'],
                                 command=lambda : self._shift(-5,0))
            pan_menu.add_command(label='Up    \t'+scut['Up'],
                                 command=lambda : self._shift(0,-5))
            pan_menu.add_command(label='Right \t'+scut['Right'],
                                 command=lambda : self._shift(5,0))
            pan_menu.add_command(label='Down  \t'+scut['Down'],
                                 command=lambda : self._shift(0,5))
        else:
            zoom_menu.add_command(label='Zoom in', accelerator='+',
                                  command=self.zoom_in)
            zoom_menu.add_command(label='Zoom out', accelerator='-',
                                  command=self.zoom_out)
            zoom_menu.add_command(label='Zoom to fit', accelerator='0',
                                  command=self.zoom_to_fit)
            pan_menu.add_command(label='Left', accelerator=scut['Left'],
                                 command=lambda : self._shift(-5,0))
            pan_menu.add_command(label='Up', accelerator=scut['Up'],
                                 command=lambda : self._shift(0,-5))
            pan_menu.add_command(label='Right', accelerator=scut['Right'],
                                 command=lambda : self._shift(5,0))
            pan_menu.add_command(label='Down', accelerator=scut['Down'],
                                 command=lambda : self._shift(0,5))
        style_menu.add_separator()
        style_menu.add_cascade(label='Zoom', menu=zoom_menu)
        style_menu.add_cascade(label='Pan', menu=pan_menu)

    def alert(self):
        background = self.canvas.cget('bg')
        def reset_bg():
            self.canvas.config(bg=background)
        self.canvas.config(bg='#000000')
        self.canvas.after(100, reset_bg)

    def done(self, event=None):
        self.window.destroy()

    def reopen(self):
        try:
            self.window.deiconify()
        except Tk_.TclError:
            print('The PLink window was destroyed')

    def set_style(self):
        mode = self.style_var.get()
        if mode == 'smooth':
            self.canvas.config(background='#ffffff')
            self.enable_fancy_save_images()
            for vertex in self.Vertices:
                vertex.hide()
            for arrow in self.Arrows:
                arrow.hide()
        elif mode == 'both':
            self.canvas.config(background='#ffffff')
            self.disable_fancy_save_images()
            for vertex in self.Vertices:
                vertex.expose()
            for arrow in self.Arrows:
                arrow.make_faint()
        else:
            self.canvas.config(background='#dcecff')
            self.enable_fancy_save_images()
            for vertex in self.Vertices:
                vertex.expose()
            for arrow in self.Arrows:
                arrow.expose()
        self.full_redraw()

    def full_redraw(self):
        """
        Recolors and redraws all components, in DT order, and displays
        the legend linking colors to cusp indices.
        """
        components = self.arrow_components(include_isolated_vertices=True)
        self.colors = []
        for key in self.color_keys:
            self.canvas.delete(key)
        self.color_keys = []
        x, y, n = 10, 5, 0
        self.palette.reset()
        for component in components:
            color = self.palette.new()
            self.colors.append(color)
            component[0].start.color = color
            for arrow in component:
                arrow.color = color
                arrow.end.color = color
                arrow.draw(self.Crossings)
            if self.style_var.get() != 'smooth':
                self.color_keys.append(
                    self.canvas.create_text(x, y,
                                            text=str(n),
                                            fill=color,
                                            anchor=Tk_.NW,
                                            font='Helvetica 16 bold'))
            x, n = x+16, n+1
        for vertex in self.Vertices:
            vertex.draw()
        self.update_smooth()

    def unpickle(self,  vertices, arrows, crossings, hot=None):
        LinkManager.unpickle(self, vertices, arrows, crossings, hot)
        self.set_style()
        self.full_redraw()

    def set_info(self):
        self.clear_text()
        which_info = self.info_var.get()
        if which_info == self.current_info:
            # toggle
            self.info_var.set(0)
            self.current_info = 0
        else:
            self.current_info = which_info
            self.update_info()

    def copy_info(self, event):
        self.window.clipboard_clear()
        if self.infotext.selection_present():
            self.window.clipboard_append(self.infotext.selection_get())
            self.infotext.selection_clear()

    def clear_text(self):
        self.infotext_contents.set('')
        self.window.focus_set()

    def write_text(self, string):
        self.infotext_contents.set(string)

    def _shift(self, dx, dy):
        for vertex in self.Vertices:
            vertex.x += dx
            vertex.y += dy
        self.canvas.move('transformable', dx, dy)
        for livearrow in (self.LiveArrow1, self.LiveArrow2, self.LiveArrow3):
            if livearrow:
                x0,y0,x1,y1 = self.canvas.coords(livearrow)
                x0 += dx
                y0 += dy
                self.canvas.coords(livearrow, x0, y0, x1, y1)

    def _zoom(self, xfactor, yfactor):
        try:
            ulx, uly, lrx, lry = self.canvas.bbox('transformable')
        except TypeError:
            return
        for vertex in self.Vertices:
            vertex.x = ulx + xfactor*(vertex.x - ulx)
            vertex.y = uly + yfactor*(vertex.y - uly)
        self.update_crosspoints()
        for arrow in self.Arrows:
            arrow.draw(self.Crossings, skip_frozen=False)
        for vertex in self.Vertices:
            vertex.draw(skip_frozen=False)
        self.update_smooth()
        for livearrow in (self.LiveArrow1, self.LiveArrow2, self.LiveArrow3):
            if livearrow:
                x0,y0,x1,y1 = self.canvas.coords(livearrow)
                x0 = ulx + xfactor*(x0 - ulx)
                y0 = uly + yfactor*(y0 - uly)
                self.canvas.coords(livearrow, x0, y0, x1, y1)
        self.update_info()

    def zoom_in(self):
        self._zoom(1.2, 1.2)

    def zoom_out(self):
        self._zoom(0.8, 0.8)

    def zoom_to_fit(self):
        W, H = self.canvas.winfo_width(), self.canvas.winfo_height()
        if W < 10:
            W, H = self.canvas.winfo_reqwidth(), self.canvas.winfo_reqheight()
        # To avoid round-off artifacts, compute a floating point bbox
        x0, y0, x1, y1 = W, H, 0, 0
        for V in self.Vertices:
            x0, y0 = min(x0, V.x), min(y0, V.y)
            x1, y1 = max(x1, V.x), max(y1, V.y)
        w, h = x1-x0, y1-y0
        factor = min( (W-60)/w, (H-60)/h )
        # Make sure we get an integer bbox after zooming
        xfactor, yfactor = round(factor*w)/w, round(factor*h)/h
        self._zoom(xfactor, yfactor)
        # Now center the picture
        try:
            x0, y0, x1, y1 = self.canvas.bbox('transformable')
            self._shift( (W - x1 + x0)/2 - x0, (H - y1 + y0)/2 - y0 )
        except TypeError:
            pass

    def update_smooth(self):
        self.smoother.clear()
        mode = self.style_var.get()
        if mode == 'smooth':
            self.smoother.set_polylines(self.polylines())
        elif mode == 'both':
            self.smoother.set_polylines(self.polylines(), thickness=2)

    # Override to hijack the update_info method
    def _check_update(self):
        return True

    def update_info(self):
        self.hide_DT()
        self.hide_labels()
        self.clear_text()
        if not self._check_update():
            return
        if self.show_DT_var.get():
            dt = self.DT_code()
            if dt is not None:
                self.show_DT()
        if self.show_labels_var.get():
            self.show_labels()
        info_value = self.info_var.get()
        if info_value == 1:
            self.DT_normal()
        elif info_value == 2:
            self.DT_alpha()
        elif info_value == 3:
            self.Gauss_info()
        elif info_value == 4:
            self.PD_info()
        elif info_value == 5:
            self.BB_info()

    def show_labels(self):
        """
        Display the assigned labels next to each crossing.
        """
        for crossing in self.Crossings:
            crossing.locate()
            yshift = 0
            for arrow in crossing.over, crossing.under:
                arrow.vectorize()
                if abs(arrow.dy) < .3*abs(arrow.dx):
                    yshift = 8
            flip = ' *' if crossing.flipped else ''
            self.labels.append(self.canvas.create_text(
                    (crossing.x - 1, crossing.y - yshift),
                    anchor=Tk_.E,
                    text=str(crossing.label)
                    ))

    def show_DT(self):
        """
        Display the DT hit counters next to each crossing.  Crossings
        that need to be flipped for the planar embedding have an
        asterisk.
        """
        for crossing in self.Crossings:
            crossing.locate()
            yshift = 0
            for arrow in crossing.over, crossing.under:
                arrow.vectorize()
                if abs(arrow.dy) < .3*abs(arrow.dx):
                    yshift = 8
            flip = ' *' if crossing.flipped else ''
            self.DTlabels.append(self.canvas.create_text(
                    (crossing.x - 10, crossing.y - yshift),
                    anchor=Tk_.E,
                    text=str(crossing.hit1)
                    ))
            self.DTlabels.append(self.canvas.create_text(
                    (crossing.x + 10, crossing.y - yshift),
                    anchor=Tk_.W,
                    text=str(crossing.hit2) + flip
                    ))

    def hide_labels(self):
        for text_item in self.labels:
            self.canvas.delete(text_item)
        self.labels = []

    def hide_DT(self):
        for text_item in self.DTlabels:
            self.canvas.delete(text_item)
        self.DTlabels = []

    def not_done(self):
        tkMessageBox.showwarning(
            'Not implemented',
            'Sorry!  That feature has not been written yet.')

    def load(self, file_name=None):
        if file_name:
            loadfile = open(file_name, "r")
        else:
            loadfile = askopenfile(parent=self.window)
        if loadfile:
            contents = loadfile.read()
            loadfile.close()
            self.clear()
            self.clear_text()
            hot = self._from_string(contents)
            # make sure the window has been rendered before doing anything
            self.window.update()
            if hot:
                self.ActiveVertex = self.Vertices[hot]
                self.goto_drawing_state(*self.canvas.winfo_pointerxy())
            else:
                self.zoom_to_fit()
                self.goto_start_state()

    def save(self):
        savefile = asksaveasfile(
            parent=self.window,
            mode='w',
            title='Save As Snappea Projection File',
            defaultextension = '.lnk',
            filetypes = [
                ("Link and text files", "*.lnk *.txt", "TEXT"),
                ("All text files", "", "TEXT"),
                ("All files", "")],
            )
        if savefile:
            savefile.write(self.SnapPea_projection_file())
            savefile.close()

    def save_image(self, file_type='eps', colormode='color'):
        mode = self.style_var.get()
        target = self.smoother if mode == 'smooth' else self
        LinkViewer.save_image(self, file_type, colormode, target)

    def about(self):
        InfoDialog(self.window, 'About PLink', self.style, About)

    def howto(self):
        doc_file = os.path.join(os.path.dirname(__file__), 'doc', 'index.html')
        doc_path = os.path.abspath(doc_file)
        url = 'file:' + pathname2url(doc_path)
        try:
            webbrowser.open(url)
        except:
            tkMessageBox.showwarning('Not found!', 'Could not open URL\n(%s)'%url)

class LinkDisplay(PLinkBase):
    """
    Displays an immutable link diagram.
    """
    def __init__(self, *args, **kwargs):
        if 'title' not in kwargs:
            kwargs['title'] = 'PLink Viewer'
        PLinkBase.__init__(self, *args, **kwargs)
        self.style_var.set('smooth')

class LinkEditor(PLinkBase):
    """
    A complete graphical link drawing tool based on the one embedded in Jeff Weeks'
    original SnapPea program.
    """
    def __init__(self, *args, **kwargs):
        if 'title' not in kwargs:
            kwargs['title'] = 'PLink Editor'
        self.callback = kwargs.pop('callback', None)
        self.cb_menu = kwargs.pop('cb_menu', '')
        self.no_arcs = kwargs.pop('no_arcs', False)
        PLinkBase.__init__(self, *args, **kwargs)
        self.flipcheck = None
        self.shift_down = False
        self.vertex_mode = False
        self.under_mode = False
        self.r1_mode = False
        self.r2_mode = False
        self.r2_crossings = []
        self.r3_mode = False
        self.r3_crossings = []
        self.r3_helper_tuple = None
        self.modes = False
        self.modes_draw = []
        self.state='start_state'
        self.canvas.bind('<Button-1>', self.single_click)
        self.canvas.bind('<Double-Button-1>', self.double_click)
        self.canvas.bind('<Shift-Button-1>', self.shift_click)
        self.canvas.bind('<Motion>', self.mouse_moved)
        self.window.bind('<FocusIn>', self.focus_in)
        self.window.bind('<FocusOut>', self.focus_out)

    def _do_callback(self):
        if self._warn_arcs() == 'oops':
            return
        self.callback(self)

    def _check_update(self):
        if self.state == 'start_state':
            return  True
        elif self.state == 'dragging_state':
            x, y = self.cursorx, self.canvas.winfo_height()-self.cursory
            self.write_text( '(%d, %d)'%(x, y) )
        return False

    def _add_file_menu(self):
        file_menu = Tk_.Menu(self.menubar, tearoff=0)
        file_menu.add_command(label='Open File ...', command=self.load)
        file_menu.add_command(label='Save ...', command=self.save)
        self.build_save_image_menu(self.menubar, file_menu)
        file_menu.add_separator()
        if self.callback:
            file_menu.add_command(label='Close', command=self.done)
        else:
            file_menu.add_command(label='Quit', command=self.done)
        self.menubar.add_cascade(label='File', menu=file_menu)

    def _extend_style_menu(self, style_menu):
        style_menu.add_radiobutton(label='Smooth edit', value='both',
                                  command=self.set_style,
                                  variable=self.style_var)

    def _add_tools_menu(self):
        self.lock_var = Tk_.BooleanVar(self.window)
        self.lock_var.set(False)
        self.tools_menu = tools_menu = Tk_.Menu(self.menubar, tearoff=0)
        tools_menu.add_command(label='Make alternating',
                       command=self.make_alternating)
        tools_menu.add_command(label='Reflect', command=self.reflect)
        tools_menu.add_checkbutton(label="Preserve diagram", var=self.lock_var)
        tools_menu.add_command(label='Clear', command=self.clear)
        if self.callback:
            tools_menu.add_command(label=self.cb_menu, command=self._do_callback)
        self.menubar.add_cascade(label='Tools', menu=tools_menu)

    # def _add_reid_menu(self):
    #     self.reid_menu = reid_menu = Tk_.Menu(self.menubar, tearoff=0)
    #     reid_menu.add_command(label='Reidemeister 1',
    #                    command=self.reid_one)
    #     reid_menu.add_command(label='Reidemeister 2',
    #                    command=self.reid_two)
    #     self.menubar.add_cascade(label='Reidemeister', menu=reid_menu)

    # def reid_one(self):
    #     if self.r1_mode:
    #         self.r1_mode = False
    #         print("No longer in r1 mode")
    #     else:
    #         self.r1_mode = True
    #         print("In r1 mode")

    # def reid_two(self):
    #     if self.r2_mode:
    #         self.r2_mode = False
    #         print("No longer in r2 mode")
    #     else:
    #         self.r2_mode = True
    #         print("In r2 mode")

    def _key_release(self, event):
        """
        Handler for keyrelease events.
        """
        if not self.state == 'start_state':
            return
        if event.keysym in ('Shift_L', 'Shift_R'):
            self.shift_down = False
            self.set_start_cursor(self.cursorx, self.cursory)

    def _key_press(self, event):
        """
        Handler for keypress events.
        """
        dx, dy = 0, 0
        key = event.keysym
        if key in ('Shift_L', 'Shift_R') and self.state == 'start_state':
            self.shift_down = True
            self.set_start_cursor(self.cursorx, self.cursory)
        if key.lower() == 'v':
            if self.vertex_mode:
                self.vertex_mode = False
                self.modes = False
                self.canvas.delete(self.modes_draw[0])
                self.modes_draw = []
                # print("No longer in vertex mode")
            else:
                if self.modes:
                    self.canvas.delete(self.modes_draw[0])
                    self.modes_draw = []
                    self.vertex_mode = False
                    self.under_mode = False
                    self.r1_mode = False
                    self.r2_mode = False
                    self.r3_mode = False
                self.modes = True
                self.vertex_mode = True
                self.modes_draw.append(self.canvas.create_text(self.canvas.winfo_width() - 80, 5,
                                            text="vertex mode",
                                            fill="red",
                                            anchor=Tk_.NW,
                                            font='Helvetica 16 bold'))
                # print("In vertex mode")
        if key.lower() == 'u':
            if self.under_mode:
                self.under_mode = False
                self.modes = False
                self.canvas.delete(self.modes_draw[0])
                self.modes_draw = []
                # print("No longer in vertex mode")
            else:
                if self.modes:
                    self.canvas.delete(self.modes_draw[0])
                    self.modes_draw = []
                    self.vertex_mode = False
                    self.under_mode = False
                    self.r1_mode = False
                    self.r2_mode = False
                    self.r3_mode = False
                self.modes = True
                self.under_mode = True
                self.modes_draw.append(self.canvas.create_text(self.canvas.winfo_width() - 80, 5,
                                            text="under mode",
                                            fill="red",
                                            anchor=Tk_.NW,
                                            font='Helvetica 16 bold'))
                # print("In vertex mode")
        if key.lower() == '1':
            if self.r1_mode:
                self.r1_mode = False
                self.modes = False
                self.canvas.delete(self.modes_draw[0])
                self.modes_draw = []
                # print("No longer in vertex mode")
            else:
                if self.modes:
                    self.canvas.delete(self.modes_draw[0])
                    self.modes_draw = []
                    self.vertex_mode = False
                    self.under_mode = False
                    self.r1_mode = False
                    self.r2_mode = False
                    self.r3_mode = False
                self.modes = True
                self.r1_mode = True
                self.modes_draw.append(self.canvas.create_text(self.canvas.winfo_width() - 80, 5,
                                            text="r1 mode",
                                            fill="red",
                                            anchor=Tk_.NW,
                                            font='Helvetica 16 bold'))
                # print("In vertex mode")
        if key.lower() == '2':
            if self.r2_mode:
                self.r2_mode = False
                self.modes = False
                self.canvas.delete(self.modes_draw[0])
                self.modes_draw = []
                # print("No longer in vertex mode")
            else:
                if self.modes:
                    self.canvas.delete(self.modes_draw[0])
                    self.modes_draw = []
                    self.vertex_mode = False
                    self.under_mode = False
                    self.r1_mode = False
                    self.r2_mode = False
                    self.r3_mode = False
                self.modes = True
                self.r2_mode = True
                self.modes_draw.append(self.canvas.create_text(self.canvas.winfo_width() - 80, 5,
                                            text="r2 mode",
                                            fill="red",
                                            anchor=Tk_.NW,
                                            font='Helvetica 16 bold'))
                # print("In vertex mode")
        if key.lower() == '3':
            if self.r3_mode:
                self.r3_mode = False
                self.modes = False
                self.canvas.delete(self.modes_draw[0])
                self.modes_draw = []
                # print("No longer in vertex mode")
            else:
                if self.modes:
                    self.canvas.delete(self.modes_draw[0])
                    self.modes_draw = []
                    self.vertex_mode = False
                    self.under_mode = False
                    self.r1_mode = False
                    self.r2_mode = False
                    self.r3_mode = False
                self.modes = True
                self.r3_mode = True
                self.modes_draw.append(self.canvas.create_text(self.canvas.winfo_width() - 80, 5,
                                            text="r3 mode",
                                            fill="red",
                                            anchor=Tk_.NW,
                                            font='Helvetica 16 bold'))
                # print("In vertex mode")
        if key.lower() == 'p':
            print("Vertices", self.Vertices)
            print("Arrows", self.Arrows)
            print("Crossings", self.Crossings)
            print("Active Vertex", self.ActiveVertex)
        if key in ('Delete','BackSpace'):
            if self.state == 'drawing_state':
                last_arrow = self.ActiveVertex.in_arrow
                if last_arrow:
                    dead_arrow = self.ActiveVertex.out_arrow
                    if dead_arrow:
                        self.destroy_arrow(dead_arrow)
                    self.ActiveVertex = last_arrow.start
                    self.ActiveVertex.out_arrow = None
                    x0,y0,x1,y1 = self.canvas.coords(self.LiveArrow1)
                    x0, y0 = self.ActiveVertex.point()
                    self.canvas.coords(self.LiveArrow1, x0, y0, x1, y1)
                    self.Crossings = [c for c in self.Crossings
                                      if last_arrow not in c]
                    self.Vertices.remove(last_arrow.end)
                    self.Arrows.remove(last_arrow)
                    last_arrow.end.erase()
                    last_arrow.erase()
                    for arrow in self.Arrows:
                        arrow.draw(self.Crossings)
                if not self.ActiveVertex.in_arrow:
                    self.Vertices.remove(self.ActiveVertex)
                    self.ActiveVertex.erase()
                    self.goto_start_state()
        elif key in ('plus', 'equal'):
            self.zoom_in()
        elif key in ('minus', 'underscore'):
            self.zoom_out()
        elif key == '0':
            self.zoom_to_fit()
        if self.state != 'dragging_state':
            try:
                self._shift(*canvas_shifts[key])
            except KeyError:
                pass
            return
        else:
            if key in ('Return','Escape'):
                self.cursorx = self.ActiveVertex.x
                self.cursory = self.ActiveVertex.y
                self.end_dragging_state()
                self.shifting = False
                return
            self._smooth_shift(key)
            return 'break'
        event.x, event.y = self.cursorx, self.cursory
        self.mouse_moved(event)

    def _warn_arcs(self):
        if self.no_arcs:
            for vertex in self.Vertices:
                if vertex.is_endpoint():
                    if tkMessageBox.askretrycancel('Warning',
                         'This link has non-closed components!\n'
                         'Click "retry" to continue editing.\n'
                         'Click "cancel" to quit anyway.\n'
                         '(The link projection may be useless.)'):
                        return 'oops'
                    else:
                        break

    def done(self, event=None):
        if self._warn_arcs() == 'oops':
            return
        else:
            # Avoid errors caused by running the "after" task after
            # the window has been destroyed, e.g. if the window is
            # closed while it does not have focus.
            if self.focus_after:
                self.window.after_cancel(self.focus_after)
            self.window.destroy()

    def make_alternating(self):
        """
        Changes crossings to make the projection alternating.
        Requires that all components be closed.
        """
        try:
            crossing_components = self.crossing_components()
        except ValueError:
            tkMessageBox.showwarning(
                'Error',
                'Please close up all components first.')
            return
        need_flipping = set()
        for component in self.DT_code()[0]:
            need_flipping.update(c for c in component if c < 0)
        for crossing in self.Crossings:
            if crossing.hit2 in need_flipping or crossing.hit1 in need_flipping:
                crossing.reverse()

        self.clear_text()
        self.update_info()
        for arrow in self.Arrows:
            arrow.draw(self.Crossings)
        self.update_smooth()

    def reflect(self):
        for crossing in self.Crossings:
            crossing.reverse()
        self.clear_text()
        self.update_info()
        for arrow in self.Arrows:
            arrow.draw(self.Crossings)
        self.update_smooth()

    def clear(self):
        self.lock_var.set(False)
        for arrow in self.Arrows:
            arrow.erase()
        for vertex in self.Vertices:
            vertex.erase()
        self.canvas.delete('all')
        self.palette.reset()
        self.initialize(self.canvas)
        self.show_DT_var.set(0)
        self.show_labels_var.set(0)
        self.info_var.set(0)
        self.clear_text()
        self.goto_start_state()

    def focus_in(self, event):
        self.focus_after = self.window.after(100, self.notice_focus)

    def notice_focus(self):
        # This is used to avoid starting a new link when the user is just
        # clicking on the window to focus it.
        self.focus_after = None
        self.has_focus = True

    def focus_out(self, event):
        self.has_focus = False

    def shift_click(self, event):
        """
        Event handler for mouse shift-clicks.
        """
        if self.style_var.get() == 'smooth':
            return
        if self.lock_var.get():
            return
        if self.state == 'start_state':
            if not self.has_focus:
                return
        else:
            self.has_focus = True
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.clear_text()
        start_vertex = Vertex(x, y, self.canvas, style='hidden')
        if start_vertex in self.CrossPoints:
            #print 'shift-click in %s'%self.state
            crossing = self.Crossings[self.CrossPoints.index(start_vertex)]
            self.update_info()
            crossing.is_virtual = not crossing.is_virtual
            crossing.under.draw(self.Crossings)
            crossing.over.draw(self.Crossings)
            self.update_smooth()

    def get_over_arrow_path(self, crossing):
        arrow_path = [crossing.over]
        while crossing.under not in arrow_path:
            most_recent = arrow_path[-1]
            arrow_path.append(most_recent.end.out_arrow)
        return arrow_path

    def get_under_arrow_path(self, crossing):
        arrow_path = [crossing.under]
        while crossing.over not in arrow_path:
            most_recent = arrow_path[-1]
            arrow_path.append(most_recent.end.out_arrow)
        return arrow_path

    def over_under_has_crossings(self, over_arrow_path, under_arrow_path, clicked_cross):
        no_crossings_over = True
        no_crossings_under = True
        cross_list_copy = self.Crossings.copy()
        cross_list_copy.remove(clicked_cross)

        for crossing in cross_list_copy:
            if crossing.under in over_arrow_path:
                no_crossings_over = False
            elif crossing.over in over_arrow_path:
                no_crossings_over = False
            elif crossing.under in under_arrow_path:
                no_crossings_under = False
            elif crossing.over in under_arrow_path:
                no_crossings_under = False
            else:
                pass
        return (no_crossings_over, no_crossings_under)

    def all_oriented(self, arrow):
        """
        returns boolean tuple (can_reduce, is_under)
        """
        no_crossings_over = True
        no_crossings_under = True
        cross_list_copy = self.Crossings
        for crossing in cross_list_copy:
            if arrow == crossing.under:
                no_crossings_under = False
            elif arrow == crossing.over:
                no_crossings_over = False
            else:
                pass
        if no_crossings_over and no_crossings_under: # no crossings at all
            return (True, self.under_mode)
        elif no_crossings_over and not no_crossings_under: # crossings are under
            return (True, True)
        elif not no_crossings_over and no_crossings_under: # crossings are over
            return (True, False)
        else:
            return (False, None)

    def get_over_arrow_path_2(self, crossing_begin, crossing_end):
        arrow_path = [crossing_begin.over]
        while crossing_end.over not in arrow_path:
            most_recent = arrow_path[-1]
            arrow_path.append(most_recent.end.out_arrow)
        return arrow_path

    def get_under_arrow_path_2(self, crossing_begin, crossing_end):
        arrow_path = [crossing_begin.under]
        while crossing_end.under not in arrow_path:
            most_recent = arrow_path[-1]
            arrow_path.append(most_recent.end.out_arrow)
        return arrow_path

    def over_under_has_crossings_2(self, over_arrow_path, under_arrow_path, crossing_begin, crossing_end):
        no_crossings_over = True
        no_crossings_under = True
        cross_list_copy = self.Crossings.copy()
        o_list = []
        u_list = []
        # over case
        for o_arrow in over_arrow_path:
            o_list.extend(o_arrow.crossings_list(cross_list_copy))
        # under case
        for u_arrow in under_arrow_path:
            u_list.extend(u_arrow.crossings_list(cross_list_copy))
        begin_index_o = o_list.index(crossing_begin)
        begin_index_u = u_list.index(crossing_begin)
        end_index_o = o_list.index(crossing_end)
        end_index_u = u_list.index(crossing_end)
        o_list = o_list[begin_index_o:end_index_o + 1]
        u_list = u_list[begin_index_u:end_index_u + 1]
        return (no_crossings_over, no_crossings_under)
<<<<<<< HEAD
    
    # def chirality(self, crossing):
    #     over_color = crossing.over.color
    #     overs = []
    #     over_sum = 0
    #     over_chirality = False
    #     under_color = crossing.under.color
    #     unders = []
    #     under_sum = 0
    #     under_chirality = False
    #     for arrow in self.Arrows:
    #         if arrow.color == under_color:
    #             unders.append(arrow)
    #         if arrow.color == over_color:
    #             overs.append(arrow)
    #     for i in overs:
    #         over_sum += (i.end.x - i.start.x) * (i.end.y + i.start.y)
    #     for j in unders:
    #         under_sum += (j.end.x - j.start.x) * (j.end.y + j.start.y)
    #     if over_sum <= 0:
    #         over_chirality = True
    #     if under_sum <= 0:
    #         under_chirality = True
    #     return (over_chirality, under_chirality)
    
    def crossing_hand(self, crossing):
        sum = ((crossing.over.end.x - crossing.x) * (crossing.over.end.y + crossing.y) +
                (crossing.under.end.x - crossing.over.end.x) * (crossing.under.end.y + crossing.over.end.y) +
                (crossing.x - crossing.under.end.x) * (crossing.y + crossing.under.end.y))
        if sum > 0:
            return 1
        else:
            return -1

    def r2_helper_pos(self, crossing, v1, v2, case):
        crossing.over.end.color = crossing.under.color
        arrow1 = Arrow(crossing.over.start, v1, self.canvas, color = crossing.over.color)
        arrow2 = Arrow(crossing.over.end, v2, self.canvas, color = crossing.under.color)
        if case == 1:
            arrow3 = Arrow(v2, crossing.under.end, self.canvas, color = crossing.under.color)
        else:
            arrow3 = Arrow(crossing.under.start, v1, self.canvas, color = crossing.under.color)
        #     self.Vertices.append(new_v)
        self.Vertices.append(v1)
        self.Vertices.append(v2)
        #     new_v.expose()
        v1.expose()
        v2.expose()
        crossing.over.end.expose()
        #     self.Arrows.insert(n + count - 1, arrow1)
        self.Arrows.append(arrow1)
        self.update_crossings(arrow1)
        self.update_crosspoints()
        arrow1.expose()
        self.Arrows.append(arrow2)
        self.update_crossings(arrow2)
        self.update_crosspoints()
        arrow2.expose()
        self.Arrows.append(arrow3)
        self.update_crossings(arrow3)
        self.update_crosspoints()
        arrow3.expose()
        arrow1.start.out_arrow = arrow1
        arrow2.start.out_arrow = arrow2
        arrow3.start.out_arrow = arrow3
        arrow1.end.in_arrow = arrow1
        arrow2.end.in_arrow = arrow2
        arrow3.end.in_arrow = arrow3
        if case == 1:
            crossing.under.end = v1
            v1.in_arrow = crossing.under
        else:
            crossing.under.start = v2
            v2.out_arrow = crossing.under
        self.update_crossings(crossing.under)
        self.update_crosspoints()
        crossing.under.expose(self.Crossings)
        self.update_info()
        return
    
    def r2_helper_neg(self, crossing, v1, v2, case):
        print(crossing.under.vectorize())
        crossing.over.start.color = crossing.under.color
        arrow1 = Arrow(v1, crossing.over.start, self.canvas, color = crossing.under.color)
        arrow2 = Arrow(v2, crossing.over.end, self.canvas, color = crossing.over.color)
        if case == 1:
            arrow3 = Arrow(crossing.under.start, v1, self.canvas, color = crossing.under.color)
        else:
            arrow3 = Arrow(v2, crossing.under.end, self.canvas, color = crossing.under.color)
        #     self.Vertices.append(new_v)
        self.Vertices.append(v1)
        self.Vertices.append(v2)
        #     new_v.expose()
        v1.expose()
        v2.expose()
        crossing.over.start.expose()
        #     self.Arrows.insert(n + count - 1, arrow1)
        self.Arrows.append(arrow1)
        self.update_crossings(arrow1)
        self.update_crosspoints()
        arrow1.expose()
        self.Arrows.append(arrow2)
        self.update_crossings(arrow2)
        self.update_crosspoints()
        arrow2.expose()
        self.Arrows.append(arrow3)
        self.update_crossings(arrow3)
        self.update_crosspoints()
        arrow3.expose()
        arrow1.start.out_arrow = arrow1
        arrow2.start.out_arrow = arrow2
        arrow3.start.out_arrow = arrow3
        arrow1.end.in_arrow = arrow1
        arrow2.end.in_arrow = arrow2
        arrow3.end.in_arrow = arrow3
        print(crossing.under.crossings_list(self.Crossings))
        if case == 1:
            crossing.under.set_start(v2)
            v2.out_arrow = crossing.under
        else:
            crossing.under.set_end(v1)
            v1.in_arrow = crossing.under
        print(crossing.under.end.x, crossing.under.end.y)
        print(crossing.under.start.x, crossing.under.start.y)
        print(float(crossing.under.end.x - crossing.under.start.x))
        print(crossing.under.vectorize())
        crossing.under.draw()
        print(crossing.under.crossings_list(self.Crossings))
        self.update_crossings(crossing.under)
        self.update_crosspoints()
        # crossing.under.expose(self.Crossings)
        # self.update_info()
        print(crossing.under.crossings_list(self.Crossings))
        return

    def fix_components_r2(self, v1, v2, v3):
        # clean up messy components
        return

=======

    def chirality(self, crossing):
        over_color = crossing.over.color
        overs = []
        over_sum = 0
        over_chirality = False
        under_color = crossing.under.color
        unders = []
        under_sum = 0
        under_chirality = False
        for arrow in self.Arrows:
            if arrow.color == under_color:
                unders.append(arrow)
            if arrow.color == over_color:
                overs.append(arrow)
        for i in overs:
            over_sum += (i.end.x - i.start.x) * (i.end.y + i.start.y)
        for j in unders:
            under_sum += (j.end.x - j.start.x) * (j.end.y + j.start.y)
        if over_sum <= 0:
            over_chirality = True
        if under_sum <= 0:
            under_chirality = True
        return (over_chirality, under_chirality)
>>>>>>> 74fc553c2d13f58275983cc3693319f9d922710b

    def get_path_btwn_verts(self, v1, v2):
        v2_found = False
        path = [v1.out_arrow]
        while not v2_found:
            next_vert = path[-1].end
            if next_vert == v2:
                return path
            else:
                path.append(next_vert.out_arrow)
        return path

    def oriented_path(self, path):
        can_reduce_all = True
        default_orientation = None
        for arrow in path:
            orientation_output = self.all_oriented(arrow)
            if orientation_output[0] == False:
                return False
            else:
                if default_orientation is None:
                    default_orientation = orientation_output[1]
                elif default_orientation is not orientation_output[1]:
                    return False
                else:
                    pass
        return True

    def get_vertex_set(self, path):
        vert_set = set()
        for i in range(len(path)):
            arrow = path[i]
            if i == 0:
                vert_set.add(arrow.end)
            elif i == (len(path)-1):
                vert_set.add(arrow.start)
            else:
                vert_set.add(arrow.start)
                vert_set.add(arrow.end)
        return vert_set

    def single_click(self, event):
        """
        Event handler for mouse clicks.
        """
        if self.style_var.get() == 'smooth':
            return
        if self.state == 'start_state':
            if not self.has_focus:
                return
        else:
            self.has_focus = True
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.clear_text()
        start_vertex = Vertex(x, y, self.canvas, color='white', style='hidden')
        if self.state == 'start_state':
            if start_vertex in self.Vertices:
                #print 'single click on a vertex'
                if self.r3_mode:
                    self.r3_crossings.append(start_vertex)
                    if len(self.r3_crossings) == 2:
                        vert1 = self.Vertices[self.Vertices.index(self.r3_crossings[0])]
                        vert2 = self.Vertices[self.Vertices.index(self.r3_crossings[1])]
                        path = self.get_path_btwn_verts(vert1, vert2)
                        is_oriented = self.oriented_path(path)
                        if is_oriented:
                            vert_set = self.get_vertex_set(path)
                            for arrow in path:
                                self.destroy_arrow(arrow)
                            for vert in vert_set:
                                vert.hide()
                                self.Vertices.remove(vert)
                            self.update_info()
                            x1, y1 = vert1.point()
                            self.ActiveVertex = vert1
                            self.goto_drawing_state(x1, y1)
                    return
                else:
                    self.state = 'dragging_state'
                    self.hide_DT()
                    self.hide_labels()
                    self.update_info()
                    self.canvas.config(cursor=closed_hand_cursor)
                    self.ActiveVertex = self.Vertices[
                        self.Vertices.index(start_vertex)]
                    self.ActiveVertex.freeze()
                    self.saved_crossing_data = self.active_crossing_data()
                    x1, y1 = self.ActiveVertex.point()
                    if self.ActiveVertex.in_arrow is None and self.ActiveVertex.out_arrow is None:
                        # If this is an isolated vertex (likely created
                        # unintentionally), switch to drawing mode.
                        self.double_click(event)
                        return
                    if self.ActiveVertex.in_arrow:
                        x0, y0 = self.ActiveVertex.in_arrow.start.point()
                        self.ActiveVertex.in_arrow.freeze()
                        self.LiveArrow1 = self.canvas.create_line(x0, y0, x1, y1, fill='red')
                    if self.ActiveVertex.out_arrow:
                        x0, y0 = self.ActiveVertex.out_arrow.end.point()
                        self.ActiveVertex.out_arrow.freeze()
                        self.LiveArrow2 = self.canvas.create_line(x0, y0, x1, y1, fill='red')
                    if self.ActiveVertex.in_arrow and self.ActiveVertex.out_arrow:
                        x0, y0 = self.ActiveVertex.out_arrow.start.point()
                        self.LiveArrow3 = self.canvas.create_line(x0, y0, x1, y1, fill='red', dash=(4, 4))
                    if self.lock_var.get():
                        self.attach_cursor('start')
                return
            elif self.lock_var.get():
                return
            elif start_vertex in self.CrossPoints:
                # print('single click on a crossing')
                if self.r1_mode == True:
                    crossing = self.Crossings[self.CrossPoints.index(start_vertex)]
                    over_arrow_path = self.get_over_arrow_path(crossing)
                    under_arrow_path = self.get_under_arrow_path(crossing)

                    can_reduce_over, can_reduce_under = self.over_under_has_crossings(over_arrow_path, under_arrow_path, crossing)

                    if can_reduce_under:
                        original_under_start = crossing.under.start
                        original_over_end = crossing.over.end
                        color = crossing.over.color

                        for ind in range(len(under_arrow_path)):
                            arrow = under_arrow_path[ind]
                            if ind != (len(under_arrow_path) - 1):
                                self.Vertices.remove(arrow.end)
                                arrow.end.erase()
                            self.destroy_arrow(arrow)

                        new_vert = start_vertex
                        new_vert.set_color(color)
                        self.Vertices.append(new_vert)

                        arrow1 = Arrow(original_under_start, new_vert, self.canvas,
                                                style='hidden', color = color)
                        arrow2 = Arrow(new_vert, original_over_end, self.canvas,
                                                style='hidden', color = color)
                        self.Arrows.append(arrow1)
                        self.Arrows.append(arrow2)

                        new_vert.expose()
                        arrow1.expose()
                        arrow2.expose()

                        self.update_info()
                    elif can_reduce_over:
                        original_under_start = crossing.over.start
                        original_over_end = crossing.under.end
                        color = crossing.over.color

                        for ind in range(len(over_arrow_path)):
                            arrow = over_arrow_path[ind]
                            if ind != (len(over_arrow_path) - 1):
                                self.Vertices.remove(arrow.end)
                                arrow.end.erase()
                            self.destroy_arrow(arrow)

                        new_vert = start_vertex
                        new_vert.set_color(color)
                        self.Vertices.append(new_vert)

                        arrow1 = Arrow(original_under_start, new_vert, self.canvas,
                                                style='hidden', color = color)
                        arrow2 = Arrow(new_vert, original_over_end, self.canvas,
                                                style='hidden', color = color)
                        self.Arrows.append(arrow1)
                        self.Arrows.append(arrow2)

                        new_vert.expose()
                        arrow1.expose()
                        arrow2.expose()

                        self.update_info()
                    else:
                        tkMessageBox.showwarning(
                            'Not implemented',
                            'Sorry! R1 mode does not work in this setting.')
                    return
                elif self.r2_mode == True:
                    # start_vertex.expose()
                    self.r2_crossings.append(start_vertex)
                    # self.r2_crossings.sort()
                    if len(self.r2_crossings) == 2:
                        if can_reduce_over or can_reduce_under:
                            segments1 = cross1.under.find_segments(self.Crossings)
                            handedness1 = self.crossing_hand(cross1)
                            # clean code for handedness heuristic
                            # start_v = cross1.under.start
                            # end_v = cross2.under.end
                            # start_inner = cross1.under.start
                            # end_inner = cross1.under.start
                            for i in range(1, len(segments1)):
                                if ((segments1[i-1][2] <= cross1.x <= segments1[i][0] or
                                    segments1[i-1][3] <= cross1.y <= segments1[i][1]) or
                                    (segments1[i-1][2] >= cross1.x >= segments1[i][0] or
                                    segments1[i-1][3] >= cross1.y >= segments1[i][1])):
                                    v1 = Vertex(segments1[i-1][2], segments1[i-1][3], self.canvas, style='hidden')
                                    v2 = Vertex(segments1[i][0], segments1[i][1], self.canvas, style='hidden')
<<<<<<< HEAD
                                    v1.set_color(cross1.over.color)
                                    v2.set_color(cross1.under.color)
                                    if handedness1 == 1:
                                        print(1)
                                        self.r2_helper_pos(cross1, v1, v2, 1)
                                        break
                                        # start_inner = v1
                                    else:
                                        print(2)
                                        self.r2_helper_neg(cross1, v1, v2, 2)
                                        break
                                        # start_inner = v1
                            print(cross2)
                            segments2 = cross2.under.find_segments(self.Crossings)
                            print(cross2)
                            handedness2 = self.crossing_hand(cross2)
=======

>>>>>>> 74fc553c2d13f58275983cc3693319f9d922710b
                            for i in range(1, len(segments2)):
                                if ((segments2[i-1][2] <= cross2.x <= segments2[i][0] or
                                    segments2[i-1][3] <= cross2.y <= segments2[i][1]) or
                                    (segments2[i-1][2] >= cross2.x >= segments2[i][0] or
                                    segments2[i-1][3] >= cross2.y >= segments2[i][1])):
                                    v1 = Vertex(segments2[i-1][2], segments2[i-1][3], self.canvas, style='hidden')
                                    v2 = Vertex(segments2[i][0], segments2[i][1], self.canvas, style='hidden')
                                    v1.set_color(cross2.under.color)
                                    v2.set_color(cross2.over.color)
                                    print(segments2, cross2)
                                    if handedness2 == 1:
                                        print(3)
                                        self.r2_helper_pos(cross2, v1, v2, 1)
                                        break
                                        # end_inner = v2
                                    else:
                                        print(4)
<<<<<<< HEAD
                                        self.r2_helper_neg(cross2, v1, v2, 2)
                                        break
                                        # end_inner = v2
                            
                            # arr = Arrow(start_inner, end_inner, self.canvas, color = cross1.over.color)
                            # self.Arrows.append(arr)
                            # self.update_crossings(arr)
                            # self.update_crosspoints()
                            # arr.expose() 
=======
                                        cross2.over.start.color = cross2.under.color
                                        arrow1 = Arrow(v1, cross2.over.start, self.canvas, color = cross2.under.color)
                                        arrow2 = Arrow(v2, cross2.over.end, self.canvas, color = cross2.over.color)
                                        arrow3 = Arrow(cross2.under.start, v1, self.canvas, color = cross2.under.color)
                                        #     self.Vertices.append(new_v)
                                        self.Vertices.append(v1)
                                        self.Vertices.append(v2)
                                        #     new_v.expose()
                                        v1.expose()
                                        v2.expose()
                                        cross2.over.start.expose()
                                        #     self.Arrows.insert(n + count - 1, arrow1)
                                        self.Arrows.append(arrow1)
                                        self.update_crossings(arrow1)
                                        self.update_crosspoints()
                                        arrow1.expose()
                                        self.Arrows.append(arrow2)
                                        self.update_crossings(arrow2)
                                        self.update_crosspoints()
                                        arrow2.expose()
                                        self.Arrows.append(arrow3)
                                        self.update_crossings(arrow3)
                                        self.update_crosspoints()
                                        arrow3.expose()
                                        arrow1.start.out_arrow = arrow1
                                        arrow2.start.out_arrow = arrow2
                                        arrow3.start.out_arrow = arrow3
                                        arrow1.end.in_arrow = arrow1
                                        arrow2.end.in_arrow = arrow2
                                        arrow3.end.in_arrow = arrow3
                                        end_inner = v2

                            arr = Arrow(start_inner, end_inner, self.canvas, color = cross1.over.color)
                            self.Arrows.append(arr)
                            self.update_crossings(arr)
                            self.update_crosspoints()
                            arr.expose()
>>>>>>> 74fc553c2d13f58275983cc3693319f9d922710b
                            # delete arrows
                            self.Arrows.remove(cross1.over)
                            cross1.over.erase()
                            self.Crossings = [c for c in self.Crossings if cross1.over not in c]
                            # self.Arrows.remove(cross1.under)
                            # cross1.under.erase()
                            # self.Crossings = [c for c in self.Crossings if cross1.under not in c]
                            if cross2.over in self.Arrows:
                                self.Arrows.remove(cross2.over)
                                cross2.over.erase()
                                self.Crossings = [c for c in self.Crossings if cross2.over not in c]
                            # if cross2.under in self.Arrows:
                            #     self.Arrows.remove(cross2.under)
                            #     cross2.under.erase()
                            #     self.Crossings = [c for c in self.Crossings if cross2.under not in c]

                            # start_v.out_arrow.expose()
                            # end_v.in_arrow.expose()
                        else:
                            tkMessageBox.showwarning(
                                'Not implemented',
                                'Sorry! R2 mode does not work in this setting.')
                        self.r2_crossings.clear()
                        self.update_info()
                    return
                else:
                    crossing = self.Crossings[self.CrossPoints.index(start_vertex)]
                    if crossing.is_virtual:
                        crossing.is_virtual = False
                    else:
                        crossing.reverse()
                    self.update_info()
                    crossing.under.draw(self.Crossings)
                    crossing.over.draw(self.Crossings)
                    self.update_smooth()
                    return
            elif self.clicked_on_arrow(start_vertex):
                print("clicked on an arrow")
                if self.vertex_mode:
                    new_vert = start_vertex
                    selected_arrow = None
                    print(self.Crossings)
                    for arrow in self.Arrows:
                        if arrow.too_close(start_vertex):
                            selected_arrow = arrow
                            this_color = arrow.color
                            start = arrow.start
                            end = arrow.end
                    self.destroy_arrow(selected_arrow)
                    new_vert.set_color(this_color)
                    arrow1 = Arrow(start, new_vert, self.canvas,
                                            style='hidden', color = this_color)
                    arrow2 = Arrow(new_vert, end, self.canvas,
                                            style='hidden', color = this_color)
                    self.Vertices.append(new_vert)
                    self.Arrows.append(arrow1)
                    self.Arrows.append(arrow2)
                    potential_crossing = Crossing
                    self.update_crossings(arrow1)
                    self.update_crossings(arrow2)
                    print(self.Crossings)
                    self.update_crosspoints()
                    self.update_info()
                    new_vert.set_color(arrow2.color)
                    start_vertex.expose()
                    print(self.Crossings)
                else:
                    for arrow in self.Arrows:
                        if arrow.too_close(start_vertex):
                            arrow.end.reverse_path(self.Crossings)
                            self.update_info()
                            break
                #print 'clicked on an arrow.'
                return
            else:
                #print 'creating a new vertex'
                if not self.generic_vertex(start_vertex):
                    start_vertex.erase()
                    self.alert()
                    return
            x1, y1 = start_vertex.point()
            start_vertex.set_color(self.palette.new())
            self.Vertices.append(start_vertex)
            self.ActiveVertex = start_vertex
            self.goto_drawing_state(x1,y1)
            return
        elif self.state == 'drawing_state':
            print("Am in drawing state", self.Crossings)
            next_vertex = Vertex(x, y, self.canvas, style='hidden')
            if next_vertex == self.ActiveVertex:
                print("clicked same vertex twice")
                #print 'clicked the same vertex twice'
                next_vertex.erase()
                dead_arrow = self.ActiveVertex.out_arrow
                if dead_arrow:
                    self.destroy_arrow(dead_arrow)
                self.goto_start_state()
                return
            #print 'setting up a new arrow'
            if self.ActiveVertex.out_arrow:
                print("Setting up new arrow")
                next_arrow = self.ActiveVertex.out_arrow
                next_arrow.set_end(next_vertex)
                next_vertex.in_arrow = next_arrow
                if not next_arrow.frozen:
                    next_arrow.hide()
            else:
                print("Not sure what this does", self.Crossings)
                this_color = self.ActiveVertex.color
                next_arrow = Arrow(self.ActiveVertex, next_vertex,
                                 self.canvas, style='hidden',
                                 color=this_color)
                self.Arrows.append(next_arrow)
            next_vertex.set_color(next_arrow.color)
            if self.r3_mode:
                if next_vertex == self.r3_crossings[1]:
                    print("finished")
                    #print 'melding vertices'
                    if not self.generic_arrow(next_arrow):
                        self.alert()
                        return
                    next_vertex.erase()
                    next_vertex = self.Vertices[self.Vertices.index(next_vertex)]
                    if next_vertex.in_arrow:
                        next_vertex.reverse_path()
                    next_arrow.set_end(next_vertex)
                    next_vertex.in_arrow = next_arrow
                    if next_vertex.color != self.ActiveVertex.color:
                        self.palette.recycle(self.ActiveVertex.color)
                        next_vertex.recolor_incoming(color = next_vertex.color)
                    self.update_crossings(next_arrow)
                    next_arrow.expose(self.Crossings)
                    self.r3_crossings = []
                    self.goto_start_state()
                    return
                #print 'just extending a path, as usual'
                if not (self.generic_vertex(next_vertex) and
                        self.generic_arrow(next_arrow) ):
                    print("not done yet")
                    self.alert()
                    self.destroy_arrow(next_arrow)
                    return
            else:
                print("Not r3 hehe", self.Crossings)
                if next_vertex in [v for v in self.Vertices if v.is_endpoint()]:
                    print("melding vertices")
                    #print 'melding vertices'
                    if not self.generic_arrow(next_arrow):
                        self.alert()
                        return
                    next_vertex.erase()
                    next_vertex = self.Vertices[self.Vertices.index(next_vertex)]
                    if next_vertex.in_arrow:
                        next_vertex.reverse_path()
                    next_arrow.set_end(next_vertex)
                    next_vertex.in_arrow = next_arrow
                    if next_vertex.color != self.ActiveVertex.color:
                        self.palette.recycle(self.ActiveVertex.color)
                        next_vertex.recolor_incoming(color = next_vertex.color)
                    self.update_crossings(next_arrow)
                    next_arrow.expose(self.Crossings)
                    self.goto_start_state()
                    self.r3_helper_tuple = None
                    return
                #print 'just extending a path, as usual'
                print("just extending path", self.Crossings)
                if not (self.generic_vertex(next_vertex) and
                        self.generic_arrow(next_arrow) ):
                    print("do we ever hit this")
                    self.alert()
                    self.destroy_arrow(next_arrow)
                    return
            print("Hit 1", self.Crossings)
            self.update_crossings(next_arrow)
            print("Hit 2", self.Crossings)
            self.update_crosspoints()
            print("Hit 3", self.Crossings)
            next_arrow.expose(self.Crossings)
            self.Vertices.append(next_vertex)
            next_vertex.expose()
            self.ActiveVertex = next_vertex
            self.canvas.coords(self.LiveArrow1,x,y,x,y)
            return
        elif self.state == 'dragging_state':
            try:
                self.end_dragging_state()
            except ValueError:
                self.alert()

    def double_click(self, event):
        """
        Event handler for mouse double-clicks.
        """
        if self.style_var.get() == 'smooth':
            return
        if self.lock_var.get():
            return
        x = x1 = self.canvas.canvasx(event.x)
        y = y1 = self.canvas.canvasy(event.y)
        self.clear_text()
        vertex = Vertex(x, y, self.canvas, style='hidden')
        #print 'double-click in %s'%self.state
        if self.state == 'dragging_state':
            try:
                self.end_dragging_state()
            except ValueError:
                self.alert()
                return
            # The first click on a vertex put us in dragging state.
            if vertex in [v for v in self.Vertices if v.is_endpoint()]:
                #print 'double-clicked on an endpoint'
                vertex.erase()
                vertex = self.Vertices[self.Vertices.index(vertex)]
                x0, y0 = x1, y1 = vertex.point()
                if vertex.out_arrow:
                    self.update_crosspoints()
                    vertex.reverse_path()
            elif vertex in self.Vertices:
                #print 'double-clicked on a non-endpoint vertex'
                cut_vertex = self.Vertices[self.Vertices.index(vertex)]
                cut_vertex.recolor_incoming(palette=self.palette)
                cut_arrow = cut_vertex.in_arrow
                cut_vertex.in_arrow = None
                vertex = cut_arrow.start
                x1, y1 = cut_vertex.point()
                cut_arrow.freeze()
            self.ActiveVertex = vertex
            self.goto_drawing_state(x1,y1)
            return
        elif self.state == 'drawing_state':
            #print 'double-click while drawing'
            dead_arrow = self.ActiveVertex.out_arrow
            if dead_arrow:
                self.destroy_arrow(dead_arrow)
            self.goto_start_state()

    def set_start_cursor(self, x, y):
        point = Vertex(x, y, self.canvas, style='hidden')
        if self.shift_down:
            if point in self.CrossPoints:
                self.canvas.config(cursor='dot')
            else:
                self.canvas.config(cursor='')
        elif self.lock_var.get():
            if point in self.Vertices:
                self.flipcheck = None
                self.canvas.config(cursor=open_hand_cursor)
            else:
                self.canvas.config(cursor='')
        else:
            if point in self.Vertices:
                self.flipcheck = None
                self.canvas.config(cursor=open_hand_cursor)
            elif point in self.CrossPoints:
                self.flipcheck = None
                self.canvas.config(cursor='exchange')
            elif self.cursor_on_arrow(point):
                now = time.time()
                if self.flipcheck is None:
                    self.flipcheck = now
                elif now - self.flipcheck > 0.5:
                    self.canvas.config(cursor='double_arrow')
            else:
                self.flipcheck = None
                self.canvas.config(cursor='')

    def mouse_moved(self,event):
        """
        Handler for mouse motion events.
        """
        if self.style_var.get() == 'smooth':
            return
        canvas = self.canvas
        X, Y = event.x, event.y
        x, y = canvas.canvasx(X), canvas.canvasy(Y)
        self.cursorx, self.cursory = X, Y
        if self.state == 'start_state':
            self.set_start_cursor(x,y)
        elif self.state == 'drawing_state':
            x0,y0,x1,y1 = self.canvas.coords(self.LiveArrow1)
            self.canvas.coords(self.LiveArrow1, x0, y0, x, y)
        elif self.state == 'dragging_state':
            if self.shifting:
                self.window.event_generate('<Return>')
                return 'break'
            else:
                self.move_active(self.canvas.canvasx(event.x),
                                 self.canvas.canvasy(event.y))

    def active_crossing_data(self):
        """
        Return the tuple of edges crossed by the in and out
        arrows of the active vertex.
        """
        assert self.ActiveVertex is not None
        active = self.ActiveVertex
        ignore = [active.in_arrow, active.out_arrow]
        return (self.crossed_arrows(active.in_arrow, ignore),
                self.crossed_arrows(active.out_arrow, ignore))

    def move_is_ok(self):
        return self.active_crossing_data() == self.saved_crossing_data

    def move_active(self, x, y):
        active = self.ActiveVertex
        if self.lock_var.get():
            x0, y0 = active.point()
            active.x, active.y = float(x), float(y)
            if self.move_is_ok():
                if not self.generic_vertex(active):
                    active.x, active.y = x0, y0
                    if self.cursor_attached:
                        self.detach_cursor('non-generic active vertex')
                    self.canvas.delete('lock_error')
                    delta = 6
                    self.canvas.create_oval(x0-delta , y0-delta, x0+delta, y0+delta,
                                            outline='gray', fill=None, width=3,
                                            tags='lock_error')
                    return
                if not self.verify_drag():
                    active.x, active.y = x0, y0
                    if self.cursor_attached:
                        self.detach_cursor('non-generic diagram')
                    return
                if not self.cursor_attached:
                    self.attach_cursor('move is ok')
            else:
                # The move is bad, but we don't know exactly how genericity
                # failed because the cursor was moving too fast.  In this
                # case we need to redraw the vertex.
                if self.cursor_attached:
                    self.detach_cursor('bad move')
                active.x, active.y = x0, y0
                self.ActiveVertex.draw()
                return
            self.canvas.delete('lock_error')
        else:
            active.x, active.y = float(x), float(y)
        self.ActiveVertex.draw()
        if self.LiveArrow1:
            x0,y0,x1,y1 = self.canvas.coords(self.LiveArrow1)
            self.canvas.coords(self.LiveArrow1, x0, y0, x, y)
        if self.LiveArrow2:
            x0,y0,x1,y1 = self.canvas.coords(self.LiveArrow2)
            self.canvas.coords(self.LiveArrow2, x0, y0, x, y)
        if self.LiveArrow3:
            x0,y0,x1,y1 = self.canvas.coords(self.LiveArrow3)
            self.canvas.coords(self.LiveArrow3, x0, y0, x, y)
        self.update_smooth()
        self.update_info()
        self.window.update_idletasks()

    def attach_cursor(self, reason=''):
        #print 'attaching:', reason
        self.cursor_attached = True
        self.ActiveVertex.set_delta(8)

    def detach_cursor(self, reason=''):
        #print 'detaching:', reason
        self.cursor_attached = False
        self.ActiveVertex.set_delta(2)

    def _smooth_shift(self, key):
            # We can't keep up with a fast repeat.
        try:
            ddx, ddy = vertex_shifts[key]
        except KeyError:
            return
        self.shifting = True
        dx, dy = self.shift_delta
        dx += ddx
        dy += ddy
        now = time.time()
        if now - self.shift_stamp < .1:
            self.shift_delta = (dx, dy)
        else:
            self.cursorx = x = self.ActiveVertex.x + dx
            self.cursory = y = self.ActiveVertex.y + dy
            self.move_active(x,y)
            self.shift_delta = (0,0)
            self.shift_stamp = now

    def clicked_on_arrow(self, vertex):
        for arrow in self.Arrows:
            if arrow.too_close(vertex):
                return True
        return False

    def cursor_on_arrow(self, point):
        if self.lock_var.get():
            return False
        for arrow in self.Arrows:
            if arrow.too_close(point):
                return True
        return False

    def goto_start_state(self):
        self.canvas.delete("lock_error")
        self.canvas.delete(self.LiveArrow1)
        self.LiveArrow1 = None
        self.canvas.delete(self.LiveArrow2)
        self.LiveArrow2 = None
        self.canvas.delete(self.LiveArrow3)
        self.LiveArrow3 = None
        self.ActiveVertex = None
        self.update_crosspoints()
        self.state = 'start_state'
        self.set_style()
        self.update_info()
        self.canvas.config(cursor='')

    def goto_drawing_state(self, x1,y1):
        self.ActiveVertex.expose()
        self.ActiveVertex.draw()
        x0, y0 = self.ActiveVertex.point()
        self.LiveArrow1 = self.canvas.create_line(x0,y0,x1,y1,fill='red')
        self.state = 'drawing_state'
        self.canvas.config(cursor='pencil')
        self.hide_DT()
        self.hide_labels()
        self.clear_text()

    def verify_drag(self):
        active = self.ActiveVertex
        active.update_arrows()
        self.update_crossings(active.in_arrow)
        self.update_crossings(active.out_arrow)
        self.update_crosspoints()
        return (self.generic_arrow(active.in_arrow) and
                self.generic_arrow(active.out_arrow) )

    def end_dragging_state(self):
        if not self.verify_drag():
            raise ValueError
        if self.lock_var.get():
            self.detach_cursor()
            self.saved_crossing_data = None
        else:
            x, y = float(self.cursorx), float(self.cursory)
            self.ActiveVertex.x, self.ActiveVertex.y = x, y
        # start code
        if self.vertex_mode:
            # in_arr = self.ActiveVertex.in_arrow
            # out_arr = self.ActiveVertex.out_arrow
            # vertex_separation_len = Arrow.epsilon + 12
            # x_0, y_0, x_1, y_1 = self.canvas.coords(self.LiveArrow3)
            # self.canvas.coords(self.LiveArrow3, x_0, y_0, x_1, y_1)
            # dotted_start_vertex = Vertex(x_0, y_0, self.canvas, style='hidden')
            # dotted_arrow = Arrow(dotted_start_vertex, self.ActiveVertex, self.canvas, color='red')
            # self.Vertices.append(dotted_start_vertex)
            # self.Arrows.append(dotted_arrow)
            # dotted_line_crossings = self.crossed_arrows(dotted_arrow, [dotted_arrow])
            # # calculations
            # count = 1
            # hypot = math.dist([x_0, y_0], [x_1, y_1])
            # sign_x = 1 if x_1 - x_0 >= 0 else -1
            # sign_y = 1 if y_1 - y_0 >= 0 else -1
            # theta = math.atan(abs((y_1 - y_0) / (x_1 - x_0)))
            # for n in dotted_line_crossings:
            #     new_x = x_0 + (hypot + (count * vertex_separation_len)) * sign_x * math.cos(theta)
            #     new_y = y_0 + (hypot + (count * vertex_separation_len)) * sign_y * math.sin(theta)
            #     if new_x >= self.canvas.winfo_width() or new_x <= 0 or new_y >= self.canvas.winfo_height() or new_y <= 0:
            #         raise ValueError
            #     edge = self.Arrows[n + count - 1]
            #     new_v = Vertex(new_x, new_y, self.canvas, style='hidden')
            #     new_v.set_color(edge.color)
            #     arrow1 = Arrow(edge.start, new_v, self.canvas, color = edge.color)
            #     arrow2 = Arrow(new_v, edge.end, self.canvas, color = edge.color)
            #     self.Vertices.append(new_v)
            #     new_v.expose()
            #     self.Arrows.insert(n + count - 1, arrow1)
            #     self.update_crossings(arrow1)
            #     self.update_crosspoints()
            #     arrow1.expose()
            #     self.Arrows.insert(n + count, arrow2)
            #     self.update_crossings(arrow2)
            #     self.update_crosspoints()
            #     arrow2.expose()
            #     count += 1
            #     self.destroy_arrow(edge)
            #     arrow1.start.out_arrow = arrow1
            #     arrow2.end.in_arrow = arrow2
            # self.Vertices.remove(dotted_start_vertex)
            # self.destroy_arrow(dotted_arrow)
            # self.ActiveVertex.in_arrow = in_arr
            # self.ActiveVertex.out_arrow = out_arr
            # self.ActiveVertex.update_arrows()
            # self.update_info()
            c_list = []
            c_list.extend(self.crossed_arrows(self.ActiveVertex.in_arrow, [self.ActiveVertex.in_arrow]))
            c_list.extend(self.crossed_arrows(self.ActiveVertex.out_arrow, [self.ActiveVertex.out_arrow]))
            if len(c_list) != len(self.active_crossing_data()):
                raise ValueError
        # end code
        endpoint = None
        if self.ActiveVertex.is_endpoint():
            other_ends = [v for v in self.Vertices if
                          v.is_endpoint() and v is not self.ActiveVertex]
            if self.ActiveVertex in other_ends:
                endpoint = other_ends[other_ends.index(self.ActiveVertex)]
                self.ActiveVertex.swallow(endpoint, self.palette)
                self.Vertices = [v for v in self.Vertices if v is not endpoint]
            self.update_crossings(self.ActiveVertex.in_arrow)
            self.update_crossings(self.ActiveVertex.out_arrow)
        if endpoint is None and not self.generic_vertex(self.ActiveVertex):
            raise ValueError
        self.ActiveVertex.expose()
        if self.style_var.get() != 'smooth':
            if self.ActiveVertex.in_arrow:
                self.ActiveVertex.in_arrow.expose()
            if self.ActiveVertex.out_arrow:
                self.ActiveVertex.out_arrow.expose()
        self.goto_start_state()

    def generic_vertex(self, vertex):
        if vertex in [v for v in self.Vertices if v is not vertex]:
            return False
        for arrow in self.Arrows:
            if arrow.too_close(vertex, tolerance=Arrow.epsilon + 2):
                #print 'non-generic vertex'
                return False
        return True

    def generic_arrow(self, arrow):
        if arrow == None:
            return True
        locked = self.lock_var.get()
        for vertex in self.Vertices:
            if arrow.too_close(vertex):
                if locked:
                    x, y, delta = vertex.x, vertex.y, 6
                    self.canvas.delete('lock_error')
                    self.canvas.create_oval(x-delta , y-delta, x+delta, y+delta,
                                            outline='gray', fill=None, width=3,
                                            tags='lock_error')
                #print 'arrow too close to vertex %s'%vertex
                return False
        for crossing in self.Crossings:
            point = self.CrossPoints[self.Crossings.index(crossing)]
            if arrow not in crossing and arrow.too_close(point):
                if locked:
                    x, y, delta = point.x, point.y, 6
                    self.canvas.delete('lock_error')
                    self.canvas.create_oval(x-delta , y-delta, x+delta, y+delta,
                                            outline='gray', fill=None, width=3,
                                            tags='lock_error')
                #print 'arrow too close to crossing %s'%crossing
                return False
        return True

    def destroy_arrow(self, arrow):
        self.Arrows.remove(arrow)
        if arrow.end:
            arrow.end.in_arrow = None
        if arrow.start:
            arrow.start.out_arrow = None
        arrow.erase()
        self.Crossings = [c for c in self.Crossings if arrow not in c]

    def update_crossings(self, this_arrow):
        """
        Redraw any arrows which were changed by moving this_arrow.
        """
        if this_arrow == None:
            return
        cross_list = [c for c in self.Crossings if this_arrow in c]
        damage_list =[]
        find = lambda x: cross_list[cross_list.index(x)]
        for arrow in self.Arrows:
            if this_arrow == arrow:
                continue
            if self.r3_helper_tuple is not None and self.r3_helper_tuple[0]:
                new_crossing = Crossing(arrow, this_arrow)
            elif self.under_mode == False:
                new_crossing = Crossing(this_arrow, arrow)
            else:
                new_crossing = Crossing(arrow, this_arrow)
            new_crossing.locate()
            if new_crossing.x != None:
                if new_crossing in cross_list:
                    #print 'keeping %s'%new_crossing
                    find(new_crossing).locate()
                    continue
                else:
                    #print 'adding %s'%new_crossing
                    self.Crossings.append(new_crossing)
            else:
                #print 'removing %s'%new_crossing
                if new_crossing in self.Crossings:
                    if arrow == find(new_crossing).under:
                        damage_list.append(arrow)
                    self.Crossings.remove(new_crossing)
        for arrow in damage_list:
            arrow.draw(self.Crossings)

    def crossed_arrows(self, arrow, ignore_list=[]):
        """
        Return a tuple containing the arrows of the diagram which are
        crossed by the given arrow, in order along the given arrow.
        """
        if arrow is None:
            return tuple()
        arrow.vectorize()
        crosslist = []
        for n, diagram_arrow in enumerate(self.Arrows):
            if arrow == diagram_arrow or diagram_arrow in ignore_list:
                continue
            t = arrow ^ diagram_arrow
            if t is not None:
                crosslist.append((t, n))
        return tuple(n for _, n in sorted(crosslist))

    def arrow_crossings(self, arrow, ignore_list=[]):
        """
        Return a tuple containing the arrows of the diagram which are
        crossed by the given arrow, in order along the given arrow.
        """
        if arrow is None:
            return tuple()
        arrow.vectorize()
        crosslist = []
        for n, diagram_arrow in enumerate(self.Arrows):
            if arrow == diagram_arrow or diagram_arrow in ignore_list:
                continue
            t = arrow ^ diagram_arrow
            if t is not None:
                crosslist.append((t, n))
        return tuple(n for _, n in sorted(crosslist))
