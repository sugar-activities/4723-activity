#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2013  Ignacio Rodríguez <ignacio@sugarlabs.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  021101301, USA.

import os
import shutil
import json
import urllib
import tempfile
import commands

from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GConf
from gi.repository import GObject
from gi.repository import Pango

from sugar3.activity import activity
from sugar3 import env
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.toolbutton import ToolButton
from sugar3.activity.widgets import ActivityButton
from sugar3.activity.widgets import StopButton
from sugar3.graphics.alert import NotifyAlert
from sugar3.graphics.alert import ConfirmationAlert
from sugar3.graphics.icon import Icon
from sugar3.graphics.xocolor import XoColor
from sugar3.graphics.objectchooser import ObjectChooser

from sugar3.graphics.icon import CanvasIcon

from jarabe.webservice.accountsmanager import get_webaccount_services
from jarabe.webservice.accountsmanager import _get_webservice_module_paths
from jarabe.webservice.accountsmanager import _get_service_name
from jarabe.webservice.accountsmanager import _get_webaccount_paths


def get_user_color():
    client = GConf.Client.get_default()
    color = client.get_string("/desktop/sugar/user/color")
    xo_color = XoColor(color)
    return xo_color


def get_stroke_color():
    xo_color = get_user_color()
    return xo_color.get_stroke_color()


def get_fill_color():
    xo_color = get_user_color()
    return xo_color.get_fill_color()


class Install(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        self.ensure_icons()
        self._selection_canvas = SelectionCanvas()
        #box = self.get_eventbox(self._selection_canvas, 'white')
        self._selection_canvas.connect('action', self.__action)

        self.build_toolbar()
        self.set_canvas(self._selection_canvas)
        self.show_all()

    def get_eventbox(self, widget, color):
        box = Gtk.EventBox()
        box.modify_bg(Gtk.StateType.NORMAL,
            Gdk.color_parse(color))
        box.add(widget)
        return box

    def get_scroll(self, widget):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(widget)
        return scroll

    def __action(self, widget, action):
        if action == 'remove-extension':
            canvas = self.get_scroll(RemoveExtensions(self))
            self.set_canvas(canvas)
        elif action == 'download':
            canvas = self.get_scroll(DownloadExtensions(self))
            self.set_canvas(canvas)
        elif action == 'load-from-journal':
            self.open_from_journal()

        self.show_all()

    def build_toolbar(self):
        toolbox = ToolbarBox()
        toolbar = toolbox.toolbar

        activity_button = ActivityButton(self)
        toolbar.insert(activity_button, -1)
        toolbar.insert(Gtk.SeparatorToolItem(), -1)

        home = ToolButton('gtk-home')
        toolbar.insert(home, -1)
        home.connect('clicked', self.__set_home)

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        toolbar.insert(separator, -1)

        stopbtn = StopButton(self)
        toolbar.insert(stopbtn, -1)
        toolbar.show_all()

        self.set_toolbar_box(toolbox)

    def ensure_icons(self):
        user = os.path.join(env.get_profile_path(), 'extensions')
        theme = Gtk.IconTheme.get_default()
        theme.append_search_path(user)

    def __set_home(self, widget=None):
        if self._canvas != self._selection_canvas:
            self._selection_canvas = SelectionCanvas()
            self.set_canvas(self._selection_canvas)
            self._selection_canvas.connect('action', self.__action)
        self.show_all()

    def open_from_journal(self):
        chooser = ObjectChooser()
        result = chooser.run()
        alert = NotifyAlert(5)
        if result == Gtk.ResponseType.ACCEPT:
            jobject = chooser.get_selected_object()
            if jobject and jobject.file_path:
                os.chdir(env.get_profile_path())
                output = commands.getoutput('tar -xf %s' % jobject.file_path)
                if 'end' in output or 'error' in output:
                    alert.props.title = _('Error')
                    alert.props.msg = _('Error extracting the extension.')
                else:
                    alert.props.title = _('Sucess')
                    alert.props.msg = _('The extension has been installed.')
            else:
                    alert.props.title = _('Error')
                    alert.props.msg = _('Error extracting the extension.')

        self.add_alert(alert)
        alert.connect('response', lambda x, y: self.remove_alert(x))


class SelectionCanvas(Gtk.Grid):

    __gsignals__ = {
        'action': (GObject.SignalFlags.RUN_FIRST, None, ([str]))
    }

    def __init__(self):
        Gtk.Grid.__init__(self)

        self.load_from_journal = self.build_zone('load-from-journal',
             _('Load from Journal'))
        self.download_from_internet = self.build_zone('download',
            _('Download from internet'))
        self.remove_extensions = self.build_zone('remove-extension',
            _('Remove installed extensions'))

        separator = Gtk.VSeparator()
        separator2 = Gtk.VSeparator()
        height = Gdk.Screen.height() - 50
        separator.set_size_request(-1, height)
        separator2.set_size_request(-1, height)

        self.attach(self.load_from_journal, 0, 0, 1, 1)
        self.attach(separator, 1, 0, 1, 1)
        self.attach(self.download_from_internet, 2, 0, 1, 1)
        self.attach(separator2, 3, 0, 1, 1)
        #self.attach(self.remove_extensions, 4, 0, 1, 1)

        services = get_webaccount_services()
        if len(services) == 0:
            self.__set_sensitive(self.remove_extensions, False)

        self.show_all()

    def build_zone(self, icon_name, text, zones=2):
        xo_color = get_user_color()
        width = Gdk.Screen.width() / zones
        icon = CanvasIcon(icon_name=icon_name, xo_color=xo_color,
            pixel_size=width)

        label = Gtk.Label()
        label.set_markup("%s" % text)
        label.modify_font(Pango.FontDescription('15'))
        label.set_justify(2)

        label.modify_fg(Gtk.StateType.NORMAL,
            Gdk.color_parse(get_fill_color()))

        vbox = Gtk.VBox()
        vbox.pack_start(icon, True, True, 0)
        vbox.pack_end(label, False, False, 5)

        box = Gtk.EventBox()
        box.add(vbox)
        #box.modify_bg(Gtk.StateType.NORMAL, Gdk.color_parse('white'))
        icon.connect('button-press-event',
            lambda x, y: self.emit('action', icon_name))
        return box

    def __set_sensitive(self, widget, sensitive=False):
        gray = Gdk.color_parse('gray')
        white = Gdk.color_parse('white')
        fill = Gdk.color_parse(get_fill_color())
        stroke = Gdk.color_parse(get_stroke_color())
        if sensitive:
            widget.set_sensitive(True)
            widget.modify_bg(Gtk.StateType.NORMAL, white)
            widget.get_child().get_children()[1].modify_fg(Gtk.StateType.NORMAL,
                fill)
        else:
            widget.set_sensitive(False)
            widget.modify_bg(Gtk.StateType.INSENSITIVE, gray)
            widget.get_child().get_children()[1].modify_fg(Gtk.StateType.NORMAL,
                stroke)


class RemoveExtensions(Gtk.Grid):
    def __init__(self, activity):
        Gtk.Grid.__init__(self)
        self.activity = activity

        pos = 0
        current = 0
        services = get_webaccount_services()
        paths = _get_webservice_module_paths()
        paths_cp = _get_webaccount_paths()

        for service in services:
            icon = service.get_icon_name()
            name = _get_service_name(paths[current])
            service_ = self.build_extension(icon, paths[current],
                paths_cp[current], name)
            self.attach(service_, 0, pos, 1, 1)

            pos += 1
            current += 1

        self.show_all()

    def build_extension(self, icon_name, service_path, cp_path, service_title):
        size = Gdk.Screen.width() / 10

        xo_color = get_user_color()
        label = Gtk.Label(service_title)
        icono = Icon(icon_name=icon_name, pixel_size=size, xo_color=xo_color)

        font = Pango.FontDescription("%d" % (size / 4))
        label.modify_font(font)

        remove = CanvasIcon(icon_name='remove-extension', xo_color=xo_color)

        hbox = Gtk.HBox()
        hbox.pack_start(icono, False, False, 5)
        hbox.pack_start(label, False, False, 5)
        hbox.pack_end(remove, False, False, 5)
        hbox.set_size_request(size * 10, -1)

        vbox = Gtk.VBox()
        vbox.pack_start(hbox, False, False, 0)
        vbox.pack_end(Gtk.HSeparator(), False, False, 3)

        remove.connect('button-press-event', self.remove_extension,
            service_path, cp_path, vbox, service_title)

        return vbox

    def remove_extension(self, widget, event, path, cp_path, vbox, title):
        alert = ConfirmationAlert()
        alert.props.title = _('¿Remove extension?')
        alert.props.msg = _('Sure?')
        alert.connect('response', self.remove_confirmation, path,
            cp_path, vbox, title)
        self.activity.add_alert(alert)

    def remove_confirmation(self, alert, response_id, path, cp_path,
            vbox, title):
        print cp_path, title
        if response_id == Gtk.ResponseType.OK:
            try:
                shutil.rmtree(path)
                shutil.rmtree(os.path.join(cp_path, title))
                alert_ = NotifyAlert(5)
                alert_.props.title = _('Removed')
                alert_.props.msg = _('Extension removed.'
                ' Please restart sugar for see efects')
                alert_.connect('response',
                    lambda x, y: self.activity.remove_alert(x))
                self.activity.add_alert(alert_)
                self.remove(vbox)
            except:
                alert_ = NotifyAlert(5)
                alert_.props.title = _('Error')
                alert_.props.msg = _('Error removing extension.')
                alert_.connect('response',
                    lambda x, y: self.activity.remove_alert(x))
                self.activity.add_alert(alert_)
        else:
            pass

        self.activity.remove_alert(alert)


class DownloadExtensions(Gtk.Grid):
    def __init__(self, activity):
        Gtk.Grid.__init__(self)
        self.activity = activity

        self.build_extensions()
        self.show_all()

    def build_extensions(self):
        extensions = os.path.join(activity.get_bundle_path(), 'extensions.json')
        f = open(extensions, 'r')
        data = json.load(f)
        f.close()
        pos = 0
        group = Gtk.SizeGroup(Gtk.SizeGroupMode.VERTICAL)

        for extension in data.keys():
            vbox = Download(data, extension, group, self.activity)
            self.attach(vbox, 0, pos, 1, 1)
            self.show_all()
            pos += 1


class Download(Gtk.VBox):
    def __init__(self, data, extension, group, activity):
        Gtk.VBox.__init__(self)
        self.activity = activity
        self.md5sum = data[extension][1]
        self.progressbar = Gtk.ProgressBar()

        size = Gdk.Screen.width() / 10

        tmp_dir = os.path.join(self.activity.get_activity_root(), 'tmp')
        fd, self.file_path = tempfile.mkstemp(dir=tmp_dir)
        os.close(fd)

        xo_color = get_user_color()
        icon = CanvasIcon(icon_name=extension, xo_color=xo_color,
            pixel_size=size)
        icon.connect('button-press-event', self.download,
            data[extension][0])
        title = Gtk.Label(extension)
        font = Pango.FontDescription("%d" % (size / 4))
        title.modify_font(font)

        hbox = Gtk.HBox()
        hbox.pack_start(icon, False, False, 5)
        hbox.pack_start(title, False, False, 15)
        hbox.pack_end(self.progressbar, False, False, 5)
        hbox.set_size_request(Gdk.Screen.width(), -1)
        group.add_widget(self.progressbar)

        self.pack_start(hbox, True, True, 0)
        self.pack_end(Gtk.HSeparator(), False, False, 5)
        self.show_all()

    def download(self, widget, event, link):
        window = self.get_window()
        window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.WATCH))
        self.progressbar.set_fraction(0.0)

        def internal_callback():
            try:
                urllib.urlretrieve(link, self.file_path,
                    reporthook=self.progress_changed)
            except Exception, info:
                alert = NotifyAlert(5)
                alert.props.title = _('Error')
                alert.props.msg = info
                alert.connect('response',
                    lambda x, y: self.activity.remove_alert(x))
                self.activity.add_alert(alert)

        GObject.idle_add(internal_callback)
        self.gobject_id = GObject.idle_add(self.check_md5sum)

    def progress_changed(self, block, block_size, total_size):
        downloaded = block * block_size
        progress = downloaded * 100 / total_size
        self.progressbar.set_fraction(progress / 100.0)
        self.progressbar.set_text(str(progress * 100))
        self.show_all()

    def check_md5sum(self):
        md5sum = commands.getoutput('md5sum %s' % self.file_path)
        md5sum = md5sum.split()[0]
        if md5sum == self.md5sum:
            alert = NotifyAlert(10)
            alert.props.title = _('Downloaded')
            alert.props.msg = _('The extension has been downloaded'
                ' and installed.')
            for alert_ in self.activity._alerts:
                self.activity.remove_alert(alert_)
            alert.connect('response',
                lambda x, y: self.activity.remove_alert(x))
            self.activity.add_alert(alert)
            os.chdir(os.path.join(env.get_profile_path()))
            os.system('tar -xf %s' % self.file_path)

            window = self.get_window()
            window.set_cursor(None)
            GObject.source_remove(self.gobject_id)

        return True