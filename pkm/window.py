# SPDX-License-Identifier: AGPL-3.0-or-later
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio

from .kernels import (
    discover_kernels,
    get_active_kernel_pkg,
    get_active_kernel_version,
)
from .terminal_dialog import TerminalDialog


def _(s):
    return s


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title(_('Parch Kernel Manager'))
        self.set_default_size(900, 700)

        self.kernels = []
        self.active_kernel_pkg = ''
        self.active_kernel_version = ''
        self.operation_in_progress = False
        self._force_close = False
        self._content_box = None
        self._kernels_section = None
        self.banner = None

        self.connect('close-request', self.on_close_request)

        self.setup_ui()
        self.load_kernels()

    def setup_ui(self):
        self.toast_overlay = Adw.ToastOverlay()

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        header = Adw.HeaderBar()

        refresh_btn = Gtk.Button()
        refresh_btn.set_icon_name('view-refresh-symbolic')
        refresh_btn.set_tooltip_text(_('Refresh'))
        refresh_btn.connect('clicked', self.on_refresh)
        header.pack_start(refresh_btn)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name('open-menu-symbolic')
        menu = Gio.Menu()
        menu.append(_('About'), 'app.about')
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        main_box.append(header)

        self.navigation_view = Adw.NavigationView()

        nav_page = Adw.NavigationPage(
            title=_('Kernel Manager'),
            child=self.create_loading_page(),
        )
        self.navigation_view.add(nav_page)
        main_box.append(self.navigation_view)

        self.toast_overlay.set_child(main_box)
        self.set_content(self.toast_overlay)

    def create_loading_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_spacing(12)

        spinner = Gtk.Spinner()
        spinner.set_size_request(32, 32)
        spinner.start()
        box.append(spinner)

        label = Gtk.Label(label=_('Loading kernels...'))
        label.add_css_class('dim-label')
        box.append(label)

        return box

    def load_kernels(self):
        thread = threading.Thread(target=self._load_worker, daemon=True)
        thread.start()

    def _load_worker(self):
        try:
            kernels = discover_kernels()
            pkg = get_active_kernel_pkg()
            ver = get_active_kernel_version()
            GLib.idle_add(self._on_kernels_loaded, kernels, pkg, ver)
        except Exception as e:
            GLib.idle_add(self._on_load_error, str(e))

    def _on_kernels_loaded(self, kernels, pkg, ver):
        self.kernels = kernels
        self.active_kernel_pkg = pkg
        self.active_kernel_version = ver

        page = self.navigation_view.get_visible_page()
        if page:
            page.set_child(self.create_main_content())

    def _on_load_error(self, error):
        page = self.navigation_view.get_visible_page()
        if page:
            status = Adw.StatusPage()
            status.set_icon_name('dialog-error-symbolic')
            status.set_title(_('Failed to Load Kernels'))
            status.set_description(error)
            page.set_child(status)

    def create_main_content(self):
        toolbar_view = Adw.ToolbarView()

        self.banner = Adw.Banner()
        if self.active_kernel_pkg:
            self.banner.set_title(
                _('Active Kernel: {} {}').format(
                    self.active_kernel_pkg, self.active_kernel_version
                )
            )
        else:
            self.banner.set_title(
                _('Kernel: {} (running)').format(self.active_kernel_version)
            )
        self.banner.set_revealed(True)
        toolbar_view.add_top_bar(self.banner)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        self._content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=24
        )
        self._content_box.set_margin_top(24)
        self._content_box.set_margin_bottom(24)
        self._content_box.set_margin_start(12)
        self._content_box.set_margin_end(12)

        self._kernels_section = self._build_kernels_section()
        self._content_box.append(self._kernels_section)

        scrolled.set_child(self._content_box)
        toolbar_view.set_content(scrolled)

        return toolbar_view

    def _build_kernels_section(self):
        clamp = Adw.Clamp(maximum_size=900)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon = Gtk.Image.new_from_icon_name('system-software-install-symbolic')
        icon.set_pixel_size(32)
        header_box.append(icon)

        label = Gtk.Label(label=_('Kernels'))
        label.add_css_class('title-2')
        label.set_halign(Gtk.Align.START)
        header_box.append(label)
        box.append(header_box)

        desc = Gtk.Label(
            label=_('Manage kernels on your Parch GNU/Linux system')
        )
        desc.add_css_class('dim-label')
        desc.set_halign(Gtk.Align.START)
        box.append(desc)

        if not self.kernels:
            status = Adw.StatusPage()
            status.set_icon_name('dialog-error-symbolic')
            status.set_title(_('No Kernels Found'))
            status.set_description(
                _('No available or installed kernels were found.')
            )
            box.append(status)
        else:
            group = Adw.PreferencesGroup()
            for kernel in self.kernels:
                group.add(self._create_kernel_row(kernel))
            box.append(group)

        clamp.set_child(box)
        return clamp

    def _create_kernel_row(self, kernel):
        row = Adw.ActionRow()
        row.set_title(kernel.name)
        row.set_subtitle(
            _('{} \u2022 Version {}').format(kernel.description, kernel.version)
        )

        icon_name = (
            'emblem-default-symbolic'
            if kernel.name == self.active_kernel_pkg
            else 'package-x-generic-symbolic'
        )
        icon = Gtk.Image.new_from_icon_name(icon_name)
        row.add_prefix(icon)

        if kernel.installed:
            if kernel.name == self.active_kernel_pkg:
                badge = Gtk.Label(label=_('Active'))
                badge.add_css_class('success')
                badge.add_css_class('caption')
                badge.set_margin_end(8)
                row.add_suffix(badge)

            installed_count = sum(1 for k in self.kernels if k.installed)
            if kernel.name != self.active_kernel_pkg and installed_count > 1:
                btn = Gtk.Button(label=_('Remove'))
                btn.add_css_class('destructive-action')
                btn.connect('clicked', self.on_remove_kernel, kernel)
                row.add_suffix(btn)
        else:
            btn = Gtk.Button(label=_('Install'))
            btn.add_css_class('suggested-action')
            btn.connect('clicked', self.on_install_kernel, kernel)
            row.add_suffix(btn)

        return row

    def on_install_kernel(self, button, kernel):
        dialog = Adw.AlertDialog.new(
            _('Install {}?').format(kernel.name),
            _('This will install {} version {} on your system.\n'
              'The installation may take several minutes.').format(
                kernel.name, kernel.version
            ),
        )
        dialog.add_response('cancel', _('Cancel'))
        dialog.add_response('install', _('Install'))
        dialog.set_response_appearance('install', Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        dialog.choose(self, None, self._on_install_response, kernel, button)

    def _on_install_response(self, dialog, result, kernel, button):
        try:
            response = dialog.choose_finish(result)
            if response == 'install':
                button.set_sensitive(False)
                button.set_label(_('Installing...'))
                self.operation_in_progress = True
                self.show_toast(_('Installing {}...').format(kernel.name))
                self._show_terminal_dialog(kernel, True, button)
        except GLib.Error:
            pass

    def on_remove_kernel(self, button, kernel):
        installed_count = sum(1 for k in self.kernels if k.installed)

        if installed_count <= 1:
            dialog = Adw.AlertDialog.new(
                _('Cannot Remove Kernel'),
                _('You must have at least one kernel installed on your system.'),
            )
            dialog.add_response('ok', _('OK'))
            dialog.set_default_response('ok')
            dialog.set_close_response('ok')
            dialog.choose(self, None, lambda *a: None)
            return

        dialog = Adw.AlertDialog.new(
            _('Remove {}?').format(kernel.name),
            _('This will remove {} version {} from your system.').format(
                kernel.name, kernel.version
            ),
        )
        dialog.add_response('cancel', _('Cancel'))
        dialog.add_response('remove', _('Remove'))
        dialog.set_response_appearance('remove', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        dialog.choose(self, None, self._on_remove_response, kernel, button)

    def _on_remove_response(self, dialog, result, kernel, button):
        try:
            response = dialog.choose_finish(result)
            if response == 'remove':
                button.set_sensitive(False)
                button.set_label(_('Removing...'))
                self.operation_in_progress = True
                self.show_toast(_('Removing {}...').format(kernel.name))
                self._show_terminal_dialog(kernel, False, button)
        except GLib.Error:
            pass

    def _show_terminal_dialog(self, kernel, install, button):
        dialog = TerminalDialog(
            self, kernel, install, self._on_operation_complete, button
        )
        dialog.present()

    def _on_operation_complete(self, status, kernel, install, button):
        self.operation_in_progress = False
        button.set_sensitive(True)
        button.set_label(_('Install') if install else _('Remove'))

        if status == 0:
            self.show_toast(
                _('{} {} successfully').format(
                    kernel.name,
                    _('installed') if install else _('removed'),
                )
            )
            kernel.installed = install
        elif status == -1:
            self.show_toast(
                _('Failed to start {} operation').format(
                    _('installation') if install else _('removal'),
                )
            )
        else:
            self.show_toast(
                _('Operation failed (exit code {})').format(status)
            )

        self.refresh_kernels()

    def refresh_kernels(self):
        thread = threading.Thread(target=self._refresh_worker, daemon=True)
        thread.start()

    def _refresh_worker(self):
        try:
            kernels = discover_kernels()
            pkg = get_active_kernel_pkg()
            ver = get_active_kernel_version()
            GLib.idle_add(self._update_kernels, kernels, pkg, ver)
        except Exception as e:
            GLib.idle_add(self.show_toast, _('Refresh failed: {}').format(e))

    def _update_kernels(self, kernels, pkg, ver):
        self.kernels = kernels
        self.active_kernel_pkg = pkg
        self.active_kernel_version = ver

        if self.banner is not None:
            if self.active_kernel_pkg:
                self.banner.set_title(
                    _('Active Kernel: {} {}').format(pkg, ver)
                )
            else:
                self.banner.set_title(
                    _('Kernel: {} (running)').format(ver)
                )
            self.banner.set_revealed(True)

        if self._content_box is not None and self._kernels_section is not None:
            self._content_box.remove(self._kernels_section)

        self._kernels_section = self._build_kernels_section()
        if self._content_box is not None:
            self._content_box.append(self._kernels_section)

    def show_toast(self, message):
        toast = Adw.Toast(title=message)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)

    def on_refresh(self, button):
        self.refresh_kernels()

    def on_about(self, action, param):
        about = Adw.AboutWindow(
            transient_for=self,
            application_name=_('Parch Kernel Manager'),
            application_icon='com.parchlinux.kernelmanager',
            developer_name=_('Parch GNU/Linux Team'),
            version='0.1.0',
            developers=['Parch Linux Developers'],
            copyright='\u00a9 2026 Parch GNU/Linux',
            license_type=Gtk.License.AGPL_3_0,
        )
        about.present()

    def on_close_request(self, window):
        if self._force_close:
            return False

        if self.operation_in_progress:
            dialog = Adw.AlertDialog.new(
                _('Operation in Progress'),
                _('An install or remove operation is running.\n'
                  'Closing will interrupt it.'),
            )
            dialog.add_response('cancel', _('Cancel'))
            dialog.add_response('close', _('Close Anyway'))
            dialog.set_response_appearance('close', Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response('cancel')
            dialog.set_close_response('cancel')
            dialog.choose(self, None, self._on_confirm_close)
            return True

        return False

    def _on_confirm_close(self, dialog, result):
        try:
            response = dialog.choose_finish(result)
            if response == 'close':
                self._force_close = True
                self.close()
        except GLib.Error:
            pass
