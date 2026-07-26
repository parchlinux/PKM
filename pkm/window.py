# SPDX-License-Identifier: AGPL-3.0-or-later
import subprocess
import threading
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio, Pango

from .kernels import (
    discover_kernels,
    get_active_kernel_pkg,
    get_active_kernel_version,
    get_default_boot_kernel,
)
from .terminal_dialog import TerminalDialog
from .custom_kernel_dialog import CustomKernelDialog
from .kernel_details_dialog import KernelDetailsDialog
from .orphan_cleaner_dialog import OrphanCleanerDialog


from .i18n import _



class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title(_('Parch Kernel Manager'))
        self.set_default_size(1050, 780)

        self.kernels = []
        self.active_kernel_pkg = ''
        self.active_kernel_version = ''
        self.default_boot_kernel = ''
        self.search_query = ''
        self.active_filter = 'all'
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
        
        # Window Title
        win_title = Adw.WindowTitle.new(_('Parch Kernel Manager'), _('v1.1.0'))
        header.set_title_widget(win_title)

        compile_btn = Gtk.Button()
        compile_btn.set_icon_name('document-edit-symbolic')
        compile_btn.set_tooltip_text(_('Compile Custom Kernel'))
        compile_btn.connect('clicked', self.on_compile_custom)
        header.pack_start(compile_btn)

        clean_btn = Gtk.Button()
        clean_btn.set_icon_name('edit-clear-symbolic')
        clean_btn.set_tooltip_text(_('Clean Orphaned Modules'))
        clean_btn.connect('clicked', self.on_clean_orphans)
        header.pack_start(clean_btn)

        refresh_btn = Gtk.Button()
        refresh_btn.set_icon_name('view-refresh-symbolic')
        refresh_btn.set_tooltip_text(_('Refresh Kernel List'))
        refresh_btn.connect('clicked', self.on_refresh)
        header.pack_start(refresh_btn)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name('open-menu-symbolic')
        menu = Gio.Menu()
        menu.append(_('Clean Orphaned Modules'), 'win.clean_orphans')
        menu.append(_('About Kernel Manager'), 'app.about')
        menu_btn.set_menu_model(menu)
        menu_btn.set_primary(True)
        header.pack_end(menu_btn)

        action = Gio.SimpleAction.new('clean_orphans', None)
        action.connect('activate', lambda *a: self.on_clean_orphans(None))
        self.add_action(action)

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
            default_k = get_default_boot_kernel()
            GLib.idle_add(self._on_kernels_loaded, kernels, pkg, ver, default_k)
        except Exception as e:
            GLib.idle_add(self._on_load_error, str(e))

    def _on_kernels_loaded(self, kernels, pkg, ver, default_k):
        self.kernels = kernels
        self.active_kernel_pkg = pkg
        self.active_kernel_version = ver
        self.default_boot_kernel = default_k

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
        clamp.set_maximum_size(1100)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_spacing(24)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(28)
        main_box.set_margin_start(18)
        main_box.set_margin_end(18)

        banner_content = self._create_banner()
        main_box.append(banner_content)

        search_filter_content = self._create_search_and_filter_bar()
        main_box.append(search_filter_content)

        kernels_content = self._build_kernels_section()
        main_box.append(kernels_content)

        clamp.set_child(main_box)
        self._scrolled_window.set_child(clamp)

        return self._scrolled_window

    def _create_banner(self):
        group = Adw.PreferencesGroup()
        row = Adw.ActionRow()
        row.set_title(_('Currently Booted Kernel'))
        if self.active_kernel_pkg:
            row.set_subtitle(f'{self.active_kernel_pkg} ({self.active_kernel_version})')
        else:
            row.set_subtitle(self.active_kernel_version)

        icon = Gtk.Image.new_from_icon_name('emblem-default-symbolic')
        icon.set_pixel_size(24)
        row.add_prefix(icon)

        badge = Gtk.Label(label=_('Running'))
        badge.add_css_class('accent')
        row.add_suffix(badge)

        group.add(row)
        return group

    def _create_search_and_filter_bar(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_spacing(12)

        # Search Bar
        search_entry = Gtk.SearchEntry()
        search_entry.set_placeholder_text(_('Search kernel packages by name, version, or description...'))
        search_entry.set_text(self.search_query)
        search_entry.connect('search-changed', self._on_search_changed)
        box.append(search_entry)

        # Filter buttons box
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        filter_box.set_spacing(8)
        filter_box.set_halign(Gtk.Align.START)

        filters = [
            ('all', _('All')),
            ('installed', _('Installed')),
            ('available', _('Available')),
            ('lts', _('LTS')),
            ('performance', _('Zen / RT')),
        ]

        for fid, flabel in filters:
            btn = Gtk.ToggleButton(label=flabel)
            if self.active_filter == fid:
                btn.set_active(True)
                btn.add_css_class('suggested-action')
            btn.connect('toggled', self._on_filter_toggled, fid)
            filter_box.append(btn)

        box.append(filter_box)
        return box

    def _on_search_changed(self, entry):
        self.search_query = entry.get_text().strip().lower()
        self.refresh_kernels()

    def _on_filter_toggled(self, button, fid):
        if button.get_active():
            self.active_filter = fid
            self.refresh_kernels()

    def _build_kernels_section(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_spacing(24)

        filtered = self._filter_kernels(self.kernels)

        if not filtered:
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            empty_box.set_spacing(16)
            empty_box.set_halign(Gtk.Align.CENTER)
            empty_box.set_valign(Gtk.Align.CENTER)
            empty_box.set_margin_top(36)
            
            icon = Gtk.Image.new_from_icon_name('system-search-symbolic')
            icon.set_pixel_size(56)
            empty_box.append(icon)
            
            title = Gtk.Label()
            title.set_markup('<span size="large" weight="bold">No Kernels Match Your Filter</span>')
            empty_box.append(title)
            
            desc = Gtk.Label(label=_('Try adjusting your search term or filter category'))
            desc.add_css_class('dim-label')
            empty_box.append(desc)
            
            return empty_box

        installed_kernels = [k for k in filtered if k.installed]
        available_kernels = [k for k in filtered if not k.installed]

        if installed_kernels:
            installed_label = Gtk.Label()
            installed_label.set_markup('<span size="large" weight="bold">Installed Kernels</span>')
            installed_label.set_halign(Gtk.Align.START)
            installed_label.set_margin_start(4)
            installed_label.set_margin_bottom(8)
            box.append(installed_label)

            installed_group = Adw.PreferencesGroup()
            for kernel in installed_kernels:
                installed_group.add(self._create_kernel_row(kernel))
            box.append(installed_group)

        if available_kernels:
            available_label = Gtk.Label()
            available_label.set_markup('<span size="large" weight="bold">Available Kernels</span>')
            available_label.set_halign(Gtk.Align.START)
            available_label.set_margin_start(4)
            available_label.set_margin_top(12 if installed_kernels else 0)
            available_label.set_margin_bottom(8)
            box.append(available_label)

            available_group = Adw.PreferencesGroup()
            for kernel in available_kernels:
                available_group.add(self._create_kernel_row(kernel))
            box.append(available_group)

        return box

    def _filter_kernels(self, kernels):
        res = []
        for k in kernels:
            # Category filter
            if self.active_filter == 'installed' and not k.installed:
                continue
            elif self.active_filter == 'available' and k.installed:
                continue
            elif self.active_filter == 'lts' and 'lts' not in k.name.lower():
                continue
            elif self.active_filter == 'performance' and not ('zen' in k.name.lower() or 'rt' in k.name.lower()):
                continue

            # Search query
            if self.search_query:
                q = self.search_query
                match = (
                    q in k.name.lower() or
                    q in k.version.lower() or
                    q in k.description.lower()
                )
                if not match:
                    continue

            res.append(k)
        return res

    def _create_kernel_row(self, kernel):
        row = Adw.ActionRow()
        row.set_title(kernel.name)
        
        if kernel.description:
            row.set_subtitle(f'{kernel.description} • {kernel.version}')
        else:
            row.set_subtitle(kernel.version)

        is_active = kernel.name == self.active_kernel_pkg
        is_default = self.default_boot_kernel and (kernel.name in self.default_boot_kernel or self.default_boot_kernel in kernel.name)
        
        if is_active:
            icon = Gtk.Image.new_from_icon_name('emblem-ok-symbolic')
        else:
            icon = Gtk.Image.new_from_icon_name('drive-harddisk-symbolic')
        icon.set_pixel_size(24)
        row.add_prefix(icon)

        suffix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        suffix_box.set_spacing(8)
        suffix_box.set_valign(Gtk.Align.CENTER)

        if is_active:
            badge = Gtk.Label(label=_('Active'))
            badge.add_css_class('accent')
            suffix_box.append(badge)

        if is_default:
            badge = Gtk.Label(label=_('Default'))
            badge.add_css_class('dim-label')
            suffix_box.append(badge)

        # Details button
        details_btn = Gtk.Button()
        details_btn.set_icon_name('dialog-information-symbolic')
        details_btn.set_tooltip_text(_('View Details'))
        details_btn.add_css_class('flat')
        details_btn.connect('clicked', lambda b: self._show_kernel_details(kernel, is_active, is_default))
        suffix_box.append(details_btn)


        if kernel.installed:
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

    def _show_kernel_details(self, kernel, is_active, is_default):
        dialog = KernelDetailsDialog(self, kernel, is_active, is_default, self._on_set_default_kernel)
        dialog.present()

    def _on_set_default_kernel(self, kernel):
        # Set default bootloader kernel
        cmd = ['pkexec', 'bootctl', 'set-default', f'{kernel.name}.conf']
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=10)
            if res.returncode == 0:
                self.show_toast(_('Set {} as default boot kernel!').format(kernel.name))
                self.refresh_kernels()
            else:
                # Try GRUB fallback
                cmd_grub = ['pkexec', 'grub-set-default', kernel.name]
                subprocess.run(cmd_grub, timeout=10)
                self.show_toast(_('Set {} as default boot kernel!').format(kernel.name))
                self.refresh_kernels()
        except Exception as e:
            self.show_toast(_('Failed to set default kernel: {}').format(e))

    def on_clean_orphans(self, button):
        dialog = OrphanCleanerDialog(self, self.kernels, self.refresh_kernels)
        dialog.present()

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
            default_k = get_default_boot_kernel()
            GLib.idle_add(self._update_kernels, kernels, pkg, ver, default_k)
        except Exception as e:
            GLib.idle_add(self.show_toast, _('Refresh failed: {}').format(e))

    def _update_kernels(self, kernels, pkg, ver, default_k):
        scroll_val = 0
        if self._scrolled_window:
            vadj = self._scrolled_window.get_vadjustment()
            if vadj:
                scroll_val = vadj.get_value()

        self.kernels = kernels
        self.active_kernel_pkg = pkg
        self.active_kernel_version = ver
        self.default_boot_kernel = default_k

        toolbar_view = self.toast_overlay.get_child()
        if toolbar_view:
            toolbar_view.set_content(self.create_main_content())
            if self._scrolled_window and scroll_val > 0:
                vadj = self._scrolled_window.get_vadjustment()
                if vadj:
                    GLib.idle_add(lambda: vadj.set_value(scroll_val) or False)

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
        release_notes = _(
            "<p>Parch Kernel Manager 1.1.0 release notes:</p>"
            "<ul>"
            "<li>Default Bootloader Kernel Selector (GRUB and systemd-boot)</li>"
            "<li>Extended Kernel Specifications and DKMS Inspector</li>"
            "<li>System Module Cleaner for orphaned /usr/lib/modules/ directories</li>"
            "<li>Search and Category Filtering (All, Installed, Available, LTS, Zen/RT)</li>"
            "<li>Custom Kernel Compilation Presets (Gaming and Low-Latency, Battery Saver)</li>"
            "<li>Native Gettext Localization and Persian (fa) Language Support</li>"
            "<li>GNOME HIG and LibAdwaita UI Revamp</li>"
            "</ul>"
        )

        about = Adw.AboutDialog(
            application_name=_('Parch Kernel Manager'),
            application_icon='com.parchlinux.kernelmanager',
            developer_name=_('Parch GNU/Linux Team'),
            version='1.1.0',
            developers=['Parch Linux Developers'],
            copyright='\u00a9 2026 Parch GNU/Linux',
            license_type=Gtk.License.AGPL_3_0,
            website='https://parchlinux.com',
            issue_url='https://github.com/parchlinux/pkm/issues',
        )
        try:
            about.set_release_notes(release_notes)
            about.set_release_notes_version('1.1.0')
        except Exception:
            pass

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
