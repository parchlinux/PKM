# SPDX-License-Identifier: AGPL-3.0-or-later
import shutil
import sys

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib

from .window import MainWindow


def _(s):
    return s


_REQUIRED_COMMANDS = ['pacman', 'pkexec', 'uname']


class ParchKernelManager(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id='com.parchlinux.kernelmanager',
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        Gtk.Settings.get_default().set_property(
            'gtk-application-prefer-dark-theme', False
        )
        self.window = None
        self.connect('startup', self._on_startup)
        self.connect('activate', self._on_activate)

    def _on_startup(self, app):
        missing = self._check_dependencies()
        if missing:
            GLib.idle_add(self._show_dependency_error, missing)
            return

        about_action = Gio.SimpleAction.new('about', None)
        about_action.connect('activate', self._on_about)
        self.add_action(about_action)

    def _check_dependencies(self):
        missing = []
        for cmd in _REQUIRED_COMMANDS:
            if not shutil.which(cmd):
                missing.append(cmd)
        return missing

    def _show_dependency_error(self, missing):
        cmd_list = '\n'.join(f'  \u2022 {cmd}' for cmd in missing)
        dialog = Adw.AlertDialog.new(
            _('Missing Dependencies'),
            _('The following required commands were not found:\n{}\n\n'
              'Please install them and try again.').format(cmd_list),
        )
        dialog.add_response('quit', _('Quit'))
        dialog.set_default_response('quit')
        dialog.set_close_response('quit')
        dialog.connect('response', lambda *a: self.quit())
        if self.window:
            dialog.choose(self.window, None, None)
        else:
            self.quit()

    def _on_about(self, action, param):
        if self.window:
            self.window.on_about(action, param)

    def _on_activate(self, app):
        if not self.window:
            self.window = MainWindow(application=self)
        self.window.present()


def main():
    app = ParchKernelManager()
    return app.run(sys.argv)
