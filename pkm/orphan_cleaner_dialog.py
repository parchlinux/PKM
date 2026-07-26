# SPDX-License-Identifier: AGPL-3.0-or-later
import subprocess
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Vte', '3.91')
from gi.repository import Gtk, Adw, GLib, Vte, Gdk

from .kernels import get_orphaned_modules


from .i18n import _



class OrphanCleanerDialog(Adw.Window):
    def __init__(self, parent, installed_kernels, on_complete):
        super().__init__(
            transient_for=parent,
            modal=True,
            title=_('System Module Cleaner'),
            default_width=600,
            default_height=480
        )

        self.parent_window = parent
        self.installed_kernels = installed_kernels
        self.on_complete = on_complete

        self.orphans = get_orphaned_modules(installed_kernels)

        self._setup_ui()

    def _setup_ui(self):
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(560)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_spacing(20)

        if not self.orphans:
            status_page = Adw.StatusPage()
            status_page.set_icon_name('emblem-ok-symbolic')
            status_page.set_title(_('System Clean'))
            status_page.set_description(_('No orphaned kernel module folders found in /usr/lib/modules/'))
            box.append(status_page)
        else:
            header_label = Gtk.Label()
            header_label.set_markup('<span size="x-large" weight="bold">Orphaned Kernel Modules</span>')
            box.append(header_label)

            desc_label = Gtk.Label(label=_('The following module folders in /usr/lib/modules/ belong to kernels that are no longer installed on your system:'))
            desc_label.add_css_class('dim-label')
            desc_label.set_wrap(True)
            box.append(desc_label)

            group = Adw.PreferencesGroup()
            group.set_title(_('Orphaned Folders'))

            for orphan in self.orphans:
                row = Adw.ActionRow()
                row.set_title(orphan['dir_name'])
                row.set_subtitle(f"Path: {orphan['path']}")
                icon = Gtk.Image.new_from_icon_name('folder-symbolic')
                icon.set_pixel_size(20)
                row.add_prefix(icon)
                group.add(row)

            box.append(group)

            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            button_box.set_spacing(12)
            button_box.set_halign(Gtk.Align.CENTER)
            button_box.set_margin_top(12)

            clean_btn = Gtk.Button(label=_('Clean Selected Modules'))
            clean_btn.add_css_class('destructive-action')
            clean_btn.connect('clicked', self._on_clean_clicked)
            button_box.append(clean_btn)

            box.append(button_box)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        toolbar_view.set_content(scrolled)
        self.set_content(toolbar_view)

    def _on_clean_clicked(self, button):
        paths_to_remove = [o['path'] for o in self.orphans]
        if not paths_to_remove:
            return

        cmd = ['pkexec', 'rm', '-rf'] + paths_to_remove

        term_window = Adw.Window(
            transient_for=self.parent_window,
            modal=True,
            title=_('Cleaning Orphaned Modules'),
            default_width=650,
            default_height=400
        )

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        term = Vte.Terminal()
        term.set_vexpand(True)
        term.set_hexpand(True)

        toolbar_view.set_content(term)
        term_window.set_content(toolbar_view)

        pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT, None)
        term.set_pty(pty)

        def on_exit(pid, status):
            GLib.timeout_add(400, lambda: term_window.close() or False)
            if self.on_complete:
                self.on_complete()

        def on_spawn(src, res):
            try:
                pid = src.spawn_finish(res)
                if isinstance(pid, tuple):
                    pid = pid[0]
                if pid:
                    GLib.child_watch_add(GLib.PRIORITY_DEFAULT, pid, on_exit)
            except Exception:
                pass

        pty.spawn_async(
            None, cmd, None,
            GLib.SpawnFlags.DO_NOT_REAP_CHILD,
            None, None, -1, None,
            on_spawn,
        )

        term_window.present()
        self.close()
