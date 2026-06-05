# SPDX-License-Identifier: AGPL-3.0-or-later
import subprocess
import threading
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Vte', '3.91')
from gi.repository import Gtk, Adw, GLib, Gio, Vte, Gdk

from .custom_kernel import (
    validate_kernel_source,
    check_build_dependencies,
    create_build_script,
    get_kernel_sources_dir,
    detect_bootloader,
)
from .terminal_dialog import TerminalDialog


def _(s):
    return s


class CustomKernelDialog(Adw.Window):
    def __init__(self, parent, on_complete):
        super().__init__(
            transient_for=parent,
            modal=True,
            title=_('Compile Custom Kernel'),
            default_width=700,
            default_height=600
        )
        
        self.parent_window = parent
        self.on_complete = on_complete
        self.source_dir = None
        self.kernel_version = None
        self.detected_bootloader = detect_bootloader()
        
        toolbar_view = Adw.ToolbarView()
        
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)
        
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        
        self.setup_page = self._create_setup_page()
        self.config_page = self._create_config_page()
        
        self.stack.add_titled(self.setup_page, 'setup', _('Setup'))
        self.stack.add_titled(self.config_page, 'config', _('Configure'))
        
        toolbar_view.set_content(self.stack)
        self.set_content(toolbar_view)
        
        default_dir = get_kernel_sources_dir()
        if default_dir:
            self.source_entry.set_text(str(default_dir))
            self._validate_source()
    
    def _create_setup_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_spacing(24)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(18)
        box.set_margin_end(18)
        
        clamp = Adw.Clamp()
        clamp.set_maximum_size(700)
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.set_spacing(18)
        
        title_label = Gtk.Label()
        title_label.set_markup('<span size="x-large" weight="bold">Compile Custom Kernel</span>')
        title_label.set_halign(Gtk.Align.CENTER)
        content_box.append(title_label)
        
        desc_label = Gtk.Label(label=_('Build and install kernel from source'))
        desc_label.add_css_class('dim-label')
        desc_label.set_halign(Gtk.Align.CENTER)
        content_box.append(desc_label)
        
        source_group = Adw.PreferencesGroup()
        source_group.set_title(_('Source Code'))
        
        source_row = Adw.ActionRow()
        source_row.set_title(_('Kernel Source Directory'))
        source_row.set_subtitle(_('Path to Linux kernel source code'))
        
        source_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        source_box.set_spacing(6)
        source_box.set_margin_top(6)
        source_box.set_margin_bottom(6)
        
        self.source_entry = Gtk.Entry()
        self.source_entry.set_hexpand(True)
        self.source_entry.set_placeholder_text(_('/usr/src/linux'))
        self.source_entry.connect('changed', lambda *a: self._validate_source())
        source_box.append(self.source_entry)
        
        browse_btn = Gtk.Button(label=_('Browse'))
        browse_btn.set_valign(Gtk.Align.CENTER)
        browse_btn.connect('clicked', self._on_browse)
        source_box.append(browse_btn)
        
        source_row.add_suffix(source_box)
        source_row.set_activatable_widget(self.source_entry)
        source_group.add(source_row)
        
        self.status_row = Adw.ActionRow()
        self.status_row.set_title(_('Validation Status'))
        self.status_icon = Gtk.Image()
        self.status_icon.set_pixel_size(20)
        self.status_row.add_prefix(self.status_icon)
        source_group.add(self.status_row)
        
        content_box.append(source_group)
        
        system_group = Adw.PreferencesGroup()
        system_group.set_title(_('System'))
        
        bootloader_info_row = Adw.ActionRow()
        bootloader_info_row.set_title(_('Bootloader'))
        if self.detected_bootloader:
            bootloader_info_row.set_subtitle(self.detected_bootloader.upper())
            icon = Gtk.Image.new_from_icon_name('emblem-ok-symbolic')
            icon.add_css_class('success')
        else:
            bootloader_info_row.set_subtitle(_('Not detected'))
            icon = Gtk.Image.new_from_icon_name('dialog-warning-symbolic')
        icon.set_pixel_size(20)
        bootloader_info_row.add_prefix(icon)
        system_group.add(bootloader_info_row)
        
        content_box.append(system_group)
        
        deps_group = Adw.PreferencesGroup()
        deps_group.set_title(_('Build Dependencies'))
        
        self.deps_status = Adw.ActionRow()
        self.deps_status.set_title(_('Checking...'))
        deps_group.add(self.deps_status)
        
        content_box.append(deps_group)
        
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_spacing(8)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(12)
        
        self.next_btn = Gtk.Button(label=_('Next'))
        self.next_btn.add_css_class('suggested-action')
        self.next_btn.set_sensitive(False)
        self.next_btn.connect('clicked', self._on_next)
        button_box.append(self.next_btn)
        
        content_box.append(button_box)
        
        clamp.set_child(content_box)
        box.append(clamp)
        scrolled.set_child(box)
        
        threading.Thread(target=self._check_dependencies_async, daemon=True).start()
        
        return scrolled
    
    def _create_config_page(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_spacing(24)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(18)
        box.set_margin_end(18)
        
        clamp = Adw.Clamp()
        clamp.set_maximum_size(700)
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.set_spacing(18)
        
        config_group = Adw.PreferencesGroup()
        config_group.set_title(_('Configuration'))
        
        self.config_method_row = Adw.ComboRow()
        self.config_method_row.set_title(_('Kernel Config'))
        config_model = Gtk.StringList()
        config_model.append(_('Default config'))
        config_model.append(_('Current kernel config'))
        config_model.append(_('Custom config file'))
        self.config_method_row.set_model(config_model)
        self.config_method_row.set_selected(0)
        config_group.add(self.config_method_row)
        
        self.localversion_row = Adw.EntryRow()
        self.localversion_row.set_title(_('Version Suffix'))
        self.localversion_row.set_text('custom')
        config_group.add(self.localversion_row)
        
        content_box.append(config_group)
        
        bootloader_group = Adw.PreferencesGroup()
        bootloader_group.set_title(_('Bootloader'))
        bootloader_desc = _('Detected: {}').format(self.detected_bootloader.upper()) if self.detected_bootloader else _('Not detected')
        bootloader_group.set_description(bootloader_desc)
        
        self.bootloader_row = Adw.ComboRow()
        self.bootloader_row.set_title(_('Update Method'))
        bootloader_model = Gtk.StringList()
        bootloader_model.append(_('Auto-detect'))
        bootloader_model.append(_('GRUB'))
        bootloader_model.append(_('systemd-boot'))
        bootloader_model.append(_('Skip'))
        self.bootloader_row.set_model(bootloader_model)
        self.bootloader_row.set_selected(0)
        
        if self.detected_bootloader:
            icon = Gtk.Image.new_from_icon_name('emblem-ok-symbolic')
            icon.add_css_class('success')
        else:
            icon = Gtk.Image.new_from_icon_name('dialog-warning-symbolic')
        icon.set_pixel_size(20)
        self.bootloader_row.add_prefix(icon)
        
        bootloader_group.add(self.bootloader_row)
        
        content_box.append(bootloader_group)
        
        info_group = Adw.PreferencesGroup()
        info_group.set_title(_('Information'))
        
        self.version_row = Adw.ActionRow()
        self.version_row.set_title(_('Kernel Version'))
        self.version_row.set_subtitle(_('Will be detected'))
        info_group.add(self.version_row)
        
        self.time_row = Adw.ActionRow()
        self.time_row.set_title(_('Build Time'))
        self.time_row.set_subtitle(_('30-90 minutes'))
        info_group.add(self.time_row)
        
        warning_row = Adw.ActionRow()
        warning_row.set_title(_('Process'))
        warning_row.set_subtitle(
            _('Compile → Install modules → Create initramfs → Update bootloader')
        )
        icon = Gtk.Image.new_from_icon_name('dialog-information-symbolic')
        icon.set_pixel_size(20)
        warning_row.add_prefix(icon)
        info_group.add(warning_row)
        
        content_box.append(info_group)
        
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_spacing(8)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(12)
        
        back_btn = Gtk.Button(label=_('Back'))
        back_btn.connect('clicked', lambda *a: self.stack.set_visible_child_name('setup'))
        button_box.append(back_btn)
        
        self.compile_btn = Gtk.Button(label=_('Compile'))
        self.compile_btn.add_css_class('suggested-action')
        self.compile_btn.connect('clicked', self._on_compile)
        button_box.append(self.compile_btn)
        
        content_box.append(button_box)
        
        clamp.set_child(content_box)
        box.append(clamp)
        scrolled.set_child(box)
        
        return scrolled
    
    def _on_browse(self, button):
        dialog = Gtk.FileDialog()
        dialog.set_title(_('Select Kernel Source Directory'))
        dialog.select_folder(self, None, self._on_folder_selected)
    
    def _on_folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                self.source_entry.set_text(path)
        except GLib.Error:
            pass
    
    def _validate_source(self):
        source_path = self.source_entry.get_text().strip()
        if not source_path:
            self.status_row.set_subtitle(_('No directory selected'))
            self.status_icon.set_from_icon_name('dialog-warning-symbolic')
            self.next_btn.set_sensitive(False)
            return
        
        valid, result = validate_kernel_source(source_path)
        
        if valid:
            self.source_dir = source_path
            self.kernel_version = result
            self.status_row.set_subtitle(_('Valid: {}').format(result))
            self.status_icon.set_from_icon_name('emblem-ok-symbolic')
            self.status_icon.add_css_class('success')
            self.next_btn.set_sensitive(True)
        else:
            self.status_row.set_subtitle(_('Invalid: {}').format(result))
            self.status_icon.set_from_icon_name('dialog-error-symbolic')
            self.status_icon.remove_css_class('success')
            self.next_btn.set_sensitive(False)
    
    def _check_dependencies_async(self):
        missing = check_build_dependencies()
        GLib.idle_add(self._update_deps_status, missing)
    
    def _update_deps_status(self, missing):
        if hasattr(self.deps_status, '_install_button'):
            self.deps_status.remove(self.deps_status._install_button)
            delattr(self.deps_status, '_install_button')
        
        if hasattr(self.deps_status, '_status_icon'):
            self.deps_status.remove(self.deps_status._status_icon)
            delattr(self.deps_status, '_status_icon')
        
        if not missing:
            self.deps_status.set_title(_('Dependencies'))
            self.deps_status.set_subtitle(_('All required packages installed'))
            icon = Gtk.Image.new_from_icon_name('emblem-ok-symbolic')
            icon.add_css_class('success')
            icon.set_pixel_size(20)
            self.deps_status.add_prefix(icon)
            self.deps_status._status_icon = icon
        else:
            self.deps_status.set_title(_('Dependencies'))
            self.deps_status.set_subtitle(_('Missing: {}').format(', '.join(missing[:3]) + ('...' if len(missing) > 3 else '')))
            icon = Gtk.Image.new_from_icon_name('dialog-warning-symbolic')
            icon.set_pixel_size(20)
            self.deps_status.add_prefix(icon)
            self.deps_status._status_icon = icon
            
            install_btn = Gtk.Button(label=_('Install'))
            install_btn.set_valign(Gtk.Align.CENTER)
            install_btn.connect('clicked', self._install_dependencies, missing)
            self.deps_status.add_suffix(install_btn)
            self.deps_status._install_button = install_btn
    
    def _install_dependencies(self, button, packages):
        if not packages:
            return
        
        dialog = Adw.AlertDialog.new(
            _('Install Build Dependencies?'),
            _('The following packages will be installed:\n\n{}').format('\n'.join(f'  • {pkg}' for pkg in packages))
        )
        dialog.add_response('cancel', _('Cancel'))
        dialog.add_response('install', _('Install'))
        dialog.set_response_appearance('install', Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        dialog.choose(self, None, self._on_install_deps_confirm, packages)
    
    def _on_install_deps_confirm(self, dialog, result, packages):
        try:
            response = dialog.choose_finish(result)
            if response != 'install':
                return
        except GLib.Error:
            return
        
        term_window = Adw.Window(
            transient_for=self.parent_window,
            modal=True,
            title=_('Installing Dependencies'),
            default_width=700,
            default_height=450
        )
        
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        
        close_btn = Gtk.Button(label=_('Close'))
        close_btn.connect('clicked', lambda btn: self._on_term_close(term_window))
        header.pack_end(close_btn)
        
        toolbar_view.add_top_bar(header)
        
        term = Vte.Terminal()
        term.set_vexpand(True)
        term.set_hexpand(True)
        term.set_scroll_on_output(True)
        term.set_scrollback_lines(10000)
        
        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', lambda ctrl, keyval, keycode, state: self._term_key_pressed(term, keyval, state))
        term.add_controller(key_controller)
        
        click_controller = Gtk.GestureClick()
        click_controller.set_button(3)
        click_controller.connect('pressed', lambda g, n, x, y: self._term_copy(term))
        term.add_controller(click_controller)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(term)
        scrolled.set_vexpand(True)
        
        toolbar_view.set_content(scrolled)
        term_window.set_content(toolbar_view)
        
        term.feed(b'Installing build dependencies...\n\n')
        
        pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT, None)
        term.set_pty(pty)
        
        state = {
            'child_pid': None,
            'completed': False
        }
        
        def on_spawn_done(src, res):
            try:
                pid = src.spawn_finish(res)
                if isinstance(pid, tuple):
                    pid = pid[0]
                state['child_pid'] = pid
                if state['child_pid']:
                    GLib.child_watch_add(GLib.PRIORITY_DEFAULT, state['child_pid'], on_process_exit)
            except GLib.Error:
                pass
        
        def on_process_exit(pid, status):
            if not state['completed']:
                state['completed'] = True
                
                try:
                    pty.close()
                except:
                    pass
                
                GLib.timeout_add(300, lambda: term_window.close() or False)
                
                def show_dialog():
                    success_dialog = Adw.AlertDialog.new(
                        _('Installation Complete'),
                        _('Build dependencies have been installed successfully.')
                    )
                    success_dialog.add_response('close', _('Close'))
                    success_dialog.set_default_response('close')
                    success_dialog.set_close_response('close')
                    success_dialog.choose(self, None, lambda *args: None)
                    
                    GLib.timeout_add(300, lambda: threading.Thread(target=self._check_dependencies_async, daemon=True).start() or False)
                
                GLib.timeout_add(400, lambda: show_dialog() or False)
        
        cmd = ['pkexec', 'pacman', '-S', '--needed'] + packages
        
        pty.spawn_async(
            None, cmd, None,
            GLib.SpawnFlags.DO_NOT_REAP_CHILD,
            None, None, -1, None,
            on_spawn_done,
        )
        
        term_window.present()
    
    def _on_term_close(self, term_window):
        term_window.close()
        threading.Thread(target=self._check_dependencies_async, daemon=True).start()
    
    def _term_copy(self, term):
        if term.get_has_selection():
            term.copy_clipboard_format(Vte.Format.TEXT)
    
    def _term_key_pressed(self, term, keyval, state):
        if state & Gdk.ModifierType.CONTROL_MASK and state & Gdk.ModifierType.SHIFT_MASK:
            if keyval == Gdk.KEY_C or keyval == Gdk.KEY_c:
                if term.get_has_selection():
                    term.copy_clipboard_format(Vte.Format.TEXT)
                return True
            elif keyval == Gdk.KEY_A or keyval == Gdk.KEY_a:
                term.select_all()
                return True
        return False
    
    def _on_deps_installed(self, status):
        pass
    
    def _on_next(self, button):
        if self.kernel_version:
            self.version_row.set_subtitle(self.kernel_version)
        self.stack.set_visible_child_name('config')
    
    def _on_compile(self, button):
        dialog = Adw.AlertDialog.new(
            _('Start Kernel Compilation?'),
            _('This will:\n\n'
              '• Compile the kernel (30-90 minutes)\n'
              '• Install kernel to /boot\n'
              '• Generate initramfs\n'
              '• Update bootloader configuration\n'
              '• Add kernel to boot menu\n\n'
              'Your system will remain usable during compilation.\n'
              'You can reboot and select the new kernel after completion.')
        )
        dialog.add_response('cancel', _('Cancel'))
        dialog.add_response('compile', _('Start Compilation'))
        dialog.set_response_appearance('compile', Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        dialog.choose(self, None, self._on_compile_confirm)
    
    def _on_compile_confirm(self, dialog, result):
        try:
            response = dialog.choose_finish(result)
            if response != 'compile':
                return
        except GLib.Error:
            return
        
        config_file = None
        selected = self.config_method_row.get_selected()
        
        if selected == 1:
            config_file = '/proc/config.gz'
            if not Path(config_file).exists():
                kernel_ver = subprocess.check_output(['uname', '-r'], timeout=5).decode().strip()
                config_file = f'/boot/config-{kernel_ver}'
        
        localversion = self.localversion_row.get_text().strip()
        
        bootloader_selection = self.bootloader_row.get_selected()
        bootloader_map = {
            0: 'auto',
            1: 'grub',
            2: 'systemd-boot',
            3: 'none',
        }
        bootloader = bootloader_map.get(bootloader_selection, 'auto')
        
        script_content = create_build_script(self.source_dir, config_file, localversion, bootloader)
        
        script_path = Path('/tmp/kernel-compile.sh')
        script_path.write_text(script_content)
        script_path.chmod(0o755)
        
        class CompileKernel:
            def __init__(self):
                self.name = f'Custom Kernel ({localversion})'
        
        class FakeButton:
            def set_sensitive(self, val): pass
            def set_label(self, val): pass
        
        kernel = CompileKernel()
        button = FakeButton()
        
        from .terminal_dialog import TerminalDialog
        compile_dialog = TerminalDialog(
            self.parent_window,
            kernel,
            True,
            self._on_compile_complete,
            button
        )
        
        compile_dialog.term.feed(b'Starting kernel compilation...\n\n')
        
        pty = compile_dialog.term.get_pty()
        if pty:
            cmd = ['pkexec', 'bash', str(script_path)]
            pty.spawn_async(
                None, cmd, None,
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None, None, -1, None,
                lambda src, res: None,
            )
        
        compile_dialog.present()
        self.close()
    

    
    def _on_compile_complete(self, status, kernel, install, button):
        if status == 0:
            if self.on_complete:
                self.on_complete(True)
        else:
            if self.on_complete:
                self.on_complete(False)
