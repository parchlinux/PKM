# SPDX-License-Identifier: AGPL-3.0-or-later
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio, Pango

from .kernels import (
    discover_kernels,
    get_active_kernel_pkg,
    get_active_kernel_version,
)
from .terminal_dialog import TerminalDialog
from .custom_kernel_dialog import CustomKernelDialog


def _(s):
    return s


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title(_('Kernel Manager'))
        self.set_default_size(1000, 750)

        self.kernels = []
        self.active_kernel_pkg = ''
        self.active_kernel_version = ''
        self.operation_in_progress = False
        self._force_close = False
        self._scrolled_window = None
        self.status_page = None

        self.connect('close-request', self.on_close_request)

        self.setup_ui()
        self.load_kernels()

    def setup_ui(self):
        self.toast_overlay = Adw.ToastOverlay()

        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()

        compile_btn = Gtk.Button()
        compile_btn.set_icon_name('document-edit-symbolic')
        compile_btn.set_tooltip_text(_('Compile Custom Kernel'))
        compile_btn.connect('clicked', self.on_compile_custom)
        header.pack_start(compile_btn)

        refresh_btn = Gtk.Button()
        refresh_btn.set_icon_name('view-refresh-symbolic')
        refresh_btn.set_tooltip_text(_('Refresh Kernel List'))
        refresh_btn.connect('clicked', self.on_refresh)
        header.pack_start(refresh_btn)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name('open-menu-symbolic')
        menu = Gio.Menu()
        menu.append(_('About Kernel Manager'), 'app.about')
        menu_btn.set_menu_model(menu)
        menu_btn.set_primary(True)
        header.pack_end(menu_btn)

        toolbar_view.add_top_bar(header)

        self.status_page = self.create_loading_page()
        toolbar_view.set_content(self.status_page)

        self.toast_overlay.set_child(toolbar_view)
        self.set_content(self.toast_overlay)

    def create_loading_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_spacing(24)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        
        spinner = Gtk.Spinner()
        spinner.set_size_request(64, 64)
        spinner.start()
        box.append(spinner)
        
        title = Gtk.Label()
        title.set_markup('<span size="x-large" weight="bold">Discovering Kernels</span>')
        box.append(title)
        
        subtitle = Gtk.Label(label=_('Scanning repositories and installed packages'))
        subtitle.add_css_class('dim-label')
        box.append(subtitle)

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

        toolbar_view = self.toast_overlay.get_child()
        if toolbar_view:
            toolbar_view.set_content(self.create_main_content())

    def _on_load_error(self, error):
        toolbar_view = self.toast_overlay.get_child()
        if toolbar_view:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.set_spacing(24)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            box.set_margin_top(48)
            box.set_margin_bottom(48)
            
            error_icon = Gtk.Image.new_from_icon_name('dialog-error-symbolic')
            error_icon.set_pixel_size(64)
            error_icon.add_css_class('error')
            box.append(error_icon)
            
            title = Gtk.Label()
            title.set_markup('<span size="x-large" weight="bold">Could Not Load Kernels</span>')
            box.append(title)
            
            desc = Gtk.Label(label=str(error))
            desc.add_css_class('dim-label')
            desc.set_wrap(True)
            desc.set_max_width_chars(50)
            box.append(desc)
            
            toolbar_view.set_content(box)

    def create_main_content(self):
        self._scrolled_window = Gtk.ScrolledWindow()
        self._scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scrolled_window.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(1200)
        clamp.set_tightening_threshold(800)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_spacing(32)
        main_box.set_margin_top(36)
        main_box.set_margin_bottom(36)
        main_box.set_margin_start(18)
        main_box.set_margin_end(18)

        banner_content = self._create_banner()
        main_box.append(banner_content)

        kernels_content = self._build_kernels_section()
        main_box.append(kernels_content)

        clamp.set_child(main_box)
        self._scrolled_window.set_child(clamp)

        return self._scrolled_window
    
    def _create_banner(self):
        banner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        banner_box.set_spacing(18)
        banner_box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name('emblem-default-symbolic')
        icon.set_pixel_size(48)
        icon.add_css_class('success')
        banner_box.append(icon)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text_box.set_spacing(6)

        title = Gtk.Label()
        title.set_markup('<span size="x-large" weight="bold">Currently Running</span>')
        title.set_halign(Gtk.Align.START)
        text_box.append(title)

        if self.active_kernel_pkg:
            kernel_label = Gtk.Label(label=f'{self.active_kernel_pkg} ({self.active_kernel_version})')
        else:
            kernel_label = Gtk.Label(label=self.active_kernel_version)
        
        kernel_label.set_halign(Gtk.Align.START)
        kernel_label.add_css_class('dim-label')
        kernel_label.set_ellipsize(Pango.EllipsizeMode.END)
        text_box.append(kernel_label)

        banner_box.append(text_box)

        frame = Gtk.Frame()
        frame.set_child(banner_box)
        frame.set_margin_start(12)
        frame.set_margin_end(12)

        return frame

    def _build_kernels_section(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_spacing(24)

        if not self.kernels:
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            empty_box.set_spacing(16)
            empty_box.set_halign(Gtk.Align.CENTER)
            empty_box.set_valign(Gtk.Align.CENTER)
            empty_box.set_margin_top(48)
            
            icon = Gtk.Image.new_from_icon_name('computer-fail-symbolic')
            icon.set_pixel_size(64)
            empty_box.append(icon)
            
            title = Gtk.Label()
            title.set_markup('<span size="x-large" weight="bold">No Kernels Available</span>')
            empty_box.append(title)
            
            desc = Gtk.Label(label=_('Could not find any kernel packages in your repositories'))
            desc.add_css_class('dim-label')
            empty_box.append(desc)
            
            return empty_box

        installed_kernels = [k for k in self.kernels if k.installed]
        available_kernels = [k for k in self.kernels if not k.installed]

        if installed_kernels:
            installed_label = Gtk.Label()
            installed_label.set_markup('<span size="x-large" weight="bold">Installed</span>')
            installed_label.set_halign(Gtk.Align.START)
            installed_label.set_margin_start(6)
            installed_label.set_margin_bottom(12)
            box.append(installed_label)

            installed_group = Adw.PreferencesGroup()
            for kernel in installed_kernels:
                installed_group.add(self._create_kernel_row(kernel))
            box.append(installed_group)

        if available_kernels:
            available_label = Gtk.Label()
            available_label.set_markup('<span size="x-large" weight="bold">Available</span>')
            available_label.set_halign(Gtk.Align.START)
            available_label.set_margin_start(6)
            available_label.set_margin_top(12 if installed_kernels else 0)
            available_label.set_margin_bottom(12)
            box.append(available_label)

            available_group = Adw.PreferencesGroup()
            for kernel in available_kernels:
                available_group.add(self._create_kernel_row(kernel))
            box.append(available_group)

        return box

    def _create_kernel_row(self, kernel):
        row = Adw.ActionRow()
        row.set_title(kernel.name)
        
        if kernel.description:
            row.set_subtitle(f'{kernel.description} • {kernel.version}')
        else:
            row.set_subtitle(kernel.version)

        is_active = kernel.name == self.active_kernel_pkg
        
        icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        icon_box.set_valign(Gtk.Align.CENTER)
        
        if is_active:
            icon = Gtk.Image.new_from_icon_name('object-select-symbolic')
            icon.add_css_class('success')
            icon.set_pixel_size(32)
        else:
            icon = Gtk.Image.new_from_icon_name('drive-harddisk-symbolic')
            icon.set_pixel_size(28)
        
        icon_box.append(icon)
        row.add_prefix(icon_box)

        suffix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        suffix_box.set_spacing(12)
        suffix_box.set_valign(Gtk.Align.CENTER)

        if kernel.installed:
            if is_active:
                badge = Gtk.Label(label=_('ACTIVE'))
                badge.add_css_class('success')
                badge.add_css_class('heading')
                badge.set_margin_end(6)
                suffix_box.append(badge)

            installed_count = sum(1 for k in self.kernels if k.installed)
            if not is_active and installed_count > 1:
                btn = Gtk.Button(label=_('Remove'))
                btn.add_css_class('destructive-action')
                btn.set_valign(Gtk.Align.CENTER)
                btn.connect('clicked', self.on_remove_kernel, kernel)
                suffix_box.append(btn)
        else:
            btn = Gtk.Button(label=_('Install'))
            btn.add_css_class('suggested-action')
            btn.set_valign(Gtk.Align.CENTER)
            btn.connect('clicked', self.on_install_kernel, kernel)
            suffix_box.append(btn)

        row.add_suffix(suffix_box)
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
                self.show_toast(_('Removing {}...').format(kernel.name))
                self._show_terminal_dialog(kernel, False, button)
        except GLib.Error:
            pass

    def _show_terminal_dialog(self, kernel, install, button):
        self.operation_in_progress = True
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

        toolbar_view = self.toast_overlay.get_child()
        if toolbar_view:
            toolbar_view.set_content(self.create_main_content())

    def show_toast(self, message):
        toast = Adw.Toast(title=message)
        toast.set_timeout(4)
        self.toast_overlay.add_toast(toast)

    def on_refresh(self, button):
        self.refresh_kernels()
    
    def on_compile_custom(self, button):
        dialog = CustomKernelDialog(self, self._on_custom_kernel_complete)
        dialog.present()
    
    def _on_custom_kernel_complete(self, success):
        if success:
            self.show_toast(_('Custom kernel compiled and installed successfully!'))
            self.refresh_kernels()
        else:
            self.show_toast(_('Kernel compilation failed or was cancelled'))

    def on_about(self, action, param):
        about = Adw.AboutDialog(
            application_name=_('Parch Kernel Manager'),
            application_icon='com.parchlinux.kernelmanager',
            developer_name=_('Parch GNU/Linux Team'),
            version='1.0.0',
            developers=['Parch Linux Developers'],
            copyright='\u00a9 2026 Parch GNU/Linux',
            license_type=Gtk.License.AGPL_3_0,
            website='https://parchlinux.com',
            issue_url='https://github.com/parchlinux/pkm/issues',
        )
        about.present(self)

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
