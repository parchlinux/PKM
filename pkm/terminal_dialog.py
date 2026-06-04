# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import signal
import subprocess

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Vte', '3.91')
from gi.repository import Gtk, Adw, GLib, Vte


def _(s):
    return s


class TerminalDialog(Gtk.Dialog):
    def __init__(self, parent, kernel, install, on_complete, button):
        title = _('{action} {name}').format(
            action=_('Installing') if install else _('Removing'),
            name=kernel.name,
        )
        super().__init__(transient_for=parent, modal=True, title=title)
        self.set_default_size(600, 400)

        self.kernel = kernel
        self.install = install
        self.on_complete = on_complete
        self.button = button
        self.child_pid = None

        header = Adw.HeaderBar()
        self.set_titlebar(header)

        cancel_btn = Gtk.Button(label=_('Cancel'))
        cancel_btn.connect('clicked', self.on_cancel)
        header.pack_start(cancel_btn)

        self.term = Vte.Terminal()
        self.term.set_vexpand(True)
        self.term.set_hexpand(True)

        content = self.get_content_area()
        content.append(self.term)

        self._setup_terminal()

    def _setup_terminal(self):
        pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT, None)
        self.term.set_pty(pty)
        self.term.connect('child-exited', self._on_child_exited)

        cmd = self._build_command()

        pty.spawn_async(
            None, cmd, None,
            GLib.SpawnFlags.DO_NOT_REAP_CHILD,
            None, None, -1, None,
            self._on_spawn_done,
        )

    def _build_command(self):
        if self.install:
            cmd = [
                'pkexec', 'pacman', '-S',
                '--needed', '--noconfirm', self.kernel.name,
            ]
            headers = f'{self.kernel.name}-headers'
            try:
                subprocess.check_output(
                    ['pacman', '-Si', headers],
                    stderr=subprocess.DEVNULL, timeout=10,
                )
                cmd.append(headers)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass
            return cmd

        cmd = [
            'pkexec', 'pacman', '-Rns',
            '--noconfirm', self.kernel.name,
        ]
        headers = f'{self.kernel.name}-headers'
        try:
            subprocess.check_output(
                ['pacman', '-Q', headers],
                stderr=subprocess.DEVNULL, timeout=5,
            )
            cmd.append(headers)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        return cmd

    def _on_spawn_done(self, src, res):
        try:
            self.child_pid = src.spawn_finish(res)
        except GLib.Error as e:
            if self.on_complete:
                self.on_complete(-1, self.kernel, self.install, self.button)
            self.close()

    def _on_child_exited(self, term, status):
        if self.child_pid is not None:
            try:
                os.waitpid(self.child_pid, 0)
            except (OSError, ChildProcessError):
                pass
            self.child_pid = None

        if self.on_complete:
            self.on_complete(status, self.kernel, self.install, self.button)
        self.close()

    def on_cancel(self, button):
        if self.child_pid is not None:
            try:
                os.kill(self.child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            self.child_pid = None
