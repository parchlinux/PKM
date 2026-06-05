# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import signal
import subprocess

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Vte', '3.91')
from gi.repository import Gtk, Adw, GLib, Vte, Gio, Gdk


def _(s):
    return s


class TerminalDialog(Adw.Window):
    def __init__(self, parent, kernel, install, on_complete, button):
        operation = _('Installing') if install else _('Removing')
        super().__init__(
            transient_for=parent,
            modal=True,
            title=f'{operation} {kernel.name}',
            default_width=750,
            default_height=550
        )

        self.kernel = kernel
        self.install = install
        self.on_complete = on_complete
        self.button = button
        self.child_pid = None
        self.callback_fired = False

        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        
        self.cancel_btn = Gtk.Button(label=_('Cancel Operation'))
        self.cancel_btn.add_css_class('destructive-action')
        self.cancel_btn.connect('clicked', self.on_cancel)
        header.pack_start(self.cancel_btn)

        toolbar_view.add_top_bar(header)

        self.term = Vte.Terminal()
        self.term.set_vexpand(True)
        self.term.set_hexpand(True)
        self.term.set_scroll_on_output(True)
        self.term.set_scrollback_lines(10000)
        self.term.set_mouse_autohide(True)
        
        click_controller = Gtk.GestureClick()
        click_controller.set_button(3)
        click_controller.connect('pressed', self._on_terminal_right_click)
        self.term.add_controller(click_controller)
        
        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', self._on_key_pressed)
        self.term.add_controller(key_controller)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.term)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        
        toolbar_view.set_content(scrolled)
        self.set_content(toolbar_view)

        self.connect('close-request', self.on_dialog_close)
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
            self._fire_callback(-1)
            self.close()

    def _on_child_exited(self, term, status):
        if self.child_pid is not None:
            try:
                os.waitpid(self.child_pid, 0)
            except (OSError, ChildProcessError):
                pass
            self.child_pid = None

        self._fire_callback(status)
        self.close()

    def _fire_callback(self, status):
        if not self.callback_fired and self.on_complete:
            self.callback_fired = True
            self.on_complete(status, self.kernel, self.install, self.button)
    
    def _on_terminal_right_click(self, gesture, n_press, x, y):
        if self.term.get_has_selection():
            self._copy_selection()
    
    def _copy_selection(self):
        if self.term.get_has_selection():
            self.term.copy_clipboard_format(Vte.Format.TEXT)
    
    def _on_key_pressed(self, controller, keyval, keycode, state):
        from gi.repository import Gdk
        
        if state & Gdk.ModifierType.CONTROL_MASK and state & Gdk.ModifierType.SHIFT_MASK:
            if keyval == Gdk.KEY_C or keyval == Gdk.KEY_c:
                self._copy_selection()
                return True
            elif keyval == Gdk.KEY_A or keyval == Gdk.KEY_a:
                self.term.select_all()
                return True
        
        return False

    def on_dialog_close(self, dialog):
        if self.child_pid is not None:
            try:
                os.kill(self.child_pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
            self.child_pid = None
        self._fire_callback(130)
        return False

    def on_cancel(self, button):
        if self.child_pid is not None:
            try:
                os.kill(self.child_pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
            self.child_pid = None
        self.close()
