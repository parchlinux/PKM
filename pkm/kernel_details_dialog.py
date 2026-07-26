# SPDX-License-Identifier: AGPL-3.0-or-later
import subprocess
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio, Pango

from .kernels import get_kernel_details, get_dkms_status, get_default_boot_kernel


from .i18n import _



class KernelDetailsDialog(Adw.Window):
    def __init__(self, parent, kernel_info, is_active=False, is_default=False, on_set_default=None):
        super().__init__(
            transient_for=parent,
            modal=True,
            title=f'{kernel_info.name} Details',
            default_width=620,
            default_height=560
        )

        self.parent_window = parent
        self.kernel_info = kernel_info
        self.is_active = is_active
        self.is_default = is_default
        self.on_set_default = on_set_default

        self.details = get_kernel_details(kernel_info)
        self.dkms_map = get_dkms_status()

        self._setup_ui()

    def _setup_ui(self):
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(580)
        clamp.set_margin_top(20)
        clamp.set_margin_bottom(20)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_spacing(20)

        # Header group
        header_group = Adw.PreferencesGroup()
        header_row = Adw.ActionRow()
        header_row.set_title(self.kernel_info.name)
        header_row.set_subtitle(self.kernel_info.version)

        icon = Gtk.Image.new_from_icon_name('drive-harddisk-symbolic')
        icon.set_pixel_size(28)
        header_row.add_prefix(icon)

        badges_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        badges_box.set_spacing(6)

        if self.is_active:
            b = Gtk.Label(label=_('Active'))
            b.add_css_class('accent')
            badges_box.append(b)

        if self.is_default:
            b = Gtk.Label(label=_('Default'))
            b.add_css_class('dim-label')
            badges_box.append(b)

        header_row.add_suffix(badges_box)
        header_group.add(header_row)
        box.append(header_group)


        # Actions group
        if self.kernel_info.installed and not self.is_default:
            action_group = Adw.PreferencesGroup()
            action_group.set_title(_('Bootloader Options'))

            def_row = Adw.ActionRow()
            def_row.set_title(_('Set as Default Kernel'))
            def_row.set_subtitle(_('Set this kernel as the default entry in GRUB/systemd-boot'))

            def_btn = Gtk.Button(label=_('Make Default'))
            def_btn.add_css_class('suggested-action')
            def_btn.set_valign(Gtk.Align.CENTER)
            def_btn.connect('clicked', self._on_set_default_clicked)
            def_row.add_suffix(def_btn)

            action_group.add(def_row)
            box.append(action_group)

        # Specifications group
        spec_group = Adw.PreferencesGroup()
        spec_group.set_title(_('Package and System Information'))


        row_status = Adw.ActionRow()
        row_status.set_title(_('Status'))
        row_status.set_subtitle(_('Installed') if self.kernel_info.installed else _('Available in Repository'))
        spec_group.add(row_status)

        row_size = Adw.ActionRow()
        row_size.set_title(_('Installed Package Size'))
        row_size.set_subtitle(self.details['installed_size'])
        spec_group.add(row_size)

        row_build = Adw.ActionRow()
        row_build.set_title(_('Build Date'))
        row_build.set_subtitle(self.details['build_date'])
        spec_group.add(row_build)

        row_headers = Adw.ActionRow()
        row_headers.set_title(_('Kernel Headers'))
        if self.details['headers_installed']:
            row_headers.set_subtitle(_('Installed'))
            icon = Gtk.Image.new_from_icon_name('emblem-ok-symbolic')
            icon.add_css_class('success')
        else:
            row_headers.set_subtitle(_('Not Installed'))
            icon = Gtk.Image.new_from_icon_name('dialog-warning-symbolic')
        icon.set_pixel_size(18)
        row_headers.add_prefix(icon)
        spec_group.add(row_headers)

        if self.details['modules_dir']:
            row_mod = Adw.ActionRow()
            row_mod.set_title(_('Modules Directory'))
            row_mod.set_subtitle(f"{self.details['modules_dir']} ({self.details['modules_size']})")
            spec_group.add(row_mod)

        box.append(spec_group)

        # DKMS Modules Group
        dkms_mods = self.dkms_map.get(self.kernel_info.version, [])
        if dkms_mods:
            dkms_group = Adw.PreferencesGroup()
            dkms_group.set_title(_('DKMS Out-of-Tree Drivers'))
            for mod in dkms_mods:
                r = Adw.ActionRow()
                r.set_title(mod['module'])
                r.set_subtitle(mod['status'])
                icon = Gtk.Image.new_from_icon_name('system-run-symbolic')
                icon.set_pixel_size(18)
                r.add_prefix(icon)
                dkms_group.add(r)
            box.append(dkms_group)

        # Cmdline parameters
        if self.is_active and self.details['cmdline']:
            cmd_group = Adw.PreferencesGroup()
            cmd_group.set_title(_('Kernel Boot Parameters (/proc/cmdline)'))
            
            cmd_entry = Gtk.TextView()
            cmd_entry.set_editable(False)
            cmd_entry.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            cmd_entry.get_buffer().set_text(self.details['cmdline'])
            cmd_entry.set_margin_top(8)
            cmd_entry.set_margin_bottom(8)
            cmd_entry.set_margin_start(12)
            cmd_entry.set_margin_end(12)

            cmd_frame = Gtk.Frame()
            cmd_frame.set_child(cmd_entry)
            cmd_group.add(cmd_frame)
            box.append(cmd_group)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        toolbar_view.set_content(scrolled)
        self.set_content(toolbar_view)

    def _on_set_default_clicked(self, button):
        if self.on_set_default:
            self.on_set_default(self.kernel_info)
        self.close()
