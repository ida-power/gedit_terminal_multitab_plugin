# -*- coding: utf8 -*-

# terminal.py - Embeded VTE terminal for gedit (Multi-Tab version)
# Based on original gedit terminal plugin, modified to support multi-tab
import os
import sys
import traceback

import gi
# 强制指定版本，避免自动适配出错
gi.require_version('Gedit', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Vte', '2.91')
# Tepl库兼容处理（6.x/5.x）
try:
    gi.require_version('Tepl', '6')
except ValueError:
    try:
        gi.require_version('Tepl', '5')
    except ValueError:
        print("[Terminal Multitab] Tepl 5/6 not found, use fallback config", file=sys.stderr)

# 导入核心库，添加异常捕获
try:
    from gi.repository import GObject, GLib, Gio, Pango, Gdk, Gtk, Gedit, Tepl, Vte
except ImportError as e:
    print(f"[Terminal Multitab] Import error: {e}", file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)
    # 缺失核心库时，至少保证Gtk/Gedit可用
    from gi.repository import GObject, GLib, Gio, Pango, Gdk, Gtk, Gedit
    Tepl = None  # 标记Tepl不可用

try:
    import gettext
    gettext.bindtextdomain('gedit-plugins')
    gettext.textdomain('gedit-plugins')
    _ = gettext.gettext
except:
    _ = lambda s: s

# 调试日志装饰器（简化日志输出）
def debug_log(func):
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        try:
            print(f"[Terminal Multitab] Running: {func_name}", file=sys.stdout)
            result = func(*args, **kwargs)
            print(f"[Terminal Multitab] Success: {func_name}", file=sys.stdout)
            return result
        except Exception as e:
            print(f"[Terminal Multitab] Error in {func_name}: {e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            raise
    return wrapper

class GeditTerminal(Vte.Terminal):
    """原终端类，保留所有原有功能（配置同步、拖拽等）"""
    defaults = {
        'audible_bell'          : False,
    }

    SETTINGS_SCHEMA_ID_BASE = "org.gnome.Terminal.ProfilesList"
    SETTING_KEY_PROFILE_USE_SYSTEM_FONT = "use-system-font"
    SETTING_KEY_PROFILE_FONT = "font"
    SETTING_KEY_PROFILE_USE_THEME_COLORS = "use-theme-colors"
    SETTING_KEY_PROFILE_FOREGROUND_COLOR = "foreground-color"
    SETTING_KEY_PROFILE_BACKGROUND_COLOR = "background-color"
    SETTING_KEY_PROFILE_PALETTE = "palette"
    SETTING_KEY_PROFILE_CURSOR_BLINK_MODE = "cursor-blink-mode"
    SETTING_KEY_PROFILE_CURSOR_SHAPE = "cursor-shape"
    SETTING_KEY_PROFILE_AUDIBLE_BELL = "audible-bell"
    SETTING_KEY_PROFILE_SCROLL_ON_KEYSTROKE = "scroll-on-keystroke"
    SETTING_KEY_PROFILE_SCROLL_ON_OUTPUT = "scroll-on-output"
    SETTING_KEY_PROFILE_SCROLLBACK_UNLIMITED = "scrollback-unlimited"
    SETTING_KEY_PROFILE_SCROLLBACK_LINES = "scrollback-lines"

    TARGET_URI_LIST = 200

    @debug_log
    def __init__(self):
        Vte.Terminal.__init__(self)

        # 基础初始化
        self.set_size(self.get_column_count(), 5)
        self.set_size_request(200, 50)

        # 拖拽支持初始化
        tl = Gtk.TargetList.new([])
        tl.add_uri_targets(self.TARGET_URI_LIST)
        self.drag_dest_set(Gtk.DestDefaults.HIGHLIGHT | Gtk.DestDefaults.DROP,
                           [], Gdk.DragAction.DEFAULT | Gdk.DragAction.COPY)
        self.drag_dest_set_target_list(tl)

        # 配置加载（容错处理）
        try:
            self.profile_settings = self.get_profile_settings()
            if self.profile_settings:
                self.profile_settings.connect("changed", self.on_profile_settings_changed)
        except Exception as e:
            print(f"[Terminal Multitab] Load profile settings failed: {e}, use default", file=sys.stderr)
            self.profile_settings = None

        # 系统字体配置
        self.system_settings = Gio.Settings.new("org.gnome.desktop.interface")
        self.system_settings.connect("changed::monospace-font-name", self.font_changed)

        # 终端配置应用
        self.reconfigure_vte()

        # 启动终端进程（容错）
        try:
            shell = Vte.get_user_shell()
            print(f"[Terminal Multitab] Spawn terminal with shell: {shell}", file=sys.stdout)
            self.spawn_sync(Vte.PtyFlags.DEFAULT, None, [shell], None, 
                           GLib.SpawnFlags.SEARCH_PATH, None, None, None)
        except Exception as e:
            print(f"[Terminal Multitab] Spawn terminal failed: {e}, use /bin/bash", file=sys.stderr)
            self.spawn_sync(Vte.PtyFlags.DEFAULT, None, ["/bin/bash"], None, 
                           GLib.SpawnFlags.SEARCH_PATH, None, None, None)

    def do_drag_data_received(self, drag_context, x, y, data, info, time):
        try:
            if info == self.TARGET_URI_LIST:
                uris = Gedit.utils_drop_get_uris(data)
                paths = ["'" + Gio.file_new_for_uri(item).get_path() + "'" for item in uris]
                self.feed_child(' '.join(paths).encode('utf-8'))
                Gtk.drag_finish(drag_context, True, False, time);
            else:
                Vte.Terminal.do_drag_data_received(self, drag_context, x, y, data, info, time)
        except Exception as e:
            print(f"[Terminal Multitab] Drag data received error: {e}", file=sys.stderr)

    def get_profile_settings(self):
        """移除自定义schema依赖，仅使用系统终端配置或默认值"""
        # 方案：完全放弃自定义fallback schema，只使用系统终端配置或硬编码默认
        # 1. 检查系统终端配置是否可用
        if Tepl is None:
            # Tepl不可用时，直接返回None（后续用硬编码默认值）
            return None

        try:
            # 尝试加载系统终端的默认配置
            profiles = Gio.Settings.new("org.gnome.Terminal.ProfilesList")
            if not Tepl or not Tepl.utils_can_use_gsettings_key(profiles, "default"):
                return None

            default_path = "/org/gnome/terminal/legacy/profiles:/:" + profiles.get_string("default") + "/"
            if not Tepl or not Tepl.utils_can_use_gsettings_schema("org.gnome.Terminal.Legacy.Profile"):
                return None

            settings = Gio.Settings.new_with_path("org.gnome.Terminal.Legacy.Profile", default_path)
            
            # 检查核心配置项是否可用
            required_keys = [
                self.SETTING_KEY_PROFILE_USE_SYSTEM_FONT,
                self.SETTING_KEY_PROFILE_FONT,
                self.SETTING_KEY_PROFILE_USE_THEME_COLORS
            ]
            for key in required_keys:
                if not Tepl or not Tepl.utils_can_use_gsettings_key(settings, key):
                    return None
            return settings
        except Exception as e:
            print(f"[Terminal Multitab] Load system terminal settings failed: {e}", file=sys.stderr)
            return None  # 返回None，后续用硬编码默认值

    def get_font(self):
        try:
            if self.profile_settings and self.profile_settings.get_boolean(self.SETTING_KEY_PROFILE_USE_SYSTEM_FONT):
                return self.system_settings.get_string("monospace-font-name")
            elif self.profile_settings:
                return self.profile_settings.get_string(self.SETTING_KEY_PROFILE_FONT)
        except:
            pass
        return "Monospace 10"  # 默认字体

    def font_changed(self, settings=None, key=None):
        try:
            font = self.get_font()
            font_desc = Pango.font_description_from_string(font)
            self.set_font(font_desc)
        except Exception as e:
            print(f"[Terminal Multitab] Font change error: {e}", file=sys.stderr)

    def reconfigure_vte(self):
        try:
            # 字体配置
            self.font_changed()

            # 颜色配置
            context = self.get_style_context()
            fg = context.get_color(Gtk.StateFlags.NORMAL)
            bg = context.get_background_color(Gtk.StateFlags.NORMAL)
            palette = []

            # 仅当profile_settings存在时才加载自定义颜色
            if self.profile_settings is not None and not self.profile_settings.get_boolean(self.SETTING_KEY_PROFILE_USE_THEME_COLORS):
                # 自定义前景色
                try:
                    fg_color = self.profile_settings.get_string(self.SETTING_KEY_PROFILE_FOREGROUND_COLOR)
                    if fg_color != "":
                        fg = Gdk.RGBA()
                        fg.parse(fg_color)
                except:
                    pass
                # 自定义背景色
                try:
                    bg_color = self.profile_settings.get_string(self.SETTING_KEY_PROFILE_BACKGROUND_COLOR)
                    if bg_color != "":
                        bg = Gdk.RGBA()
                        bg.parse(bg_color)
                except:
                    pass
                # 自定义调色板
                try:
                    str_colors = self.profile_settings.get_strv(self.SETTING_KEY_PROFILE_PALETTE)
                    if str_colors:
                        for str_color in str_colors:
                            try:
                                rgba = Gdk.RGBA()
                                rgba.parse(str_color)
                                palette.append(rgba)
                            except:
                                palette = []
                                break
                except:
                    pass

            # 应用颜色配置
            self.set_colors(fg, bg, palette)

            # 其他终端配置（容错：无配置时用硬编码默认值）
            if self.profile_settings is not None:
                try:
                    self.set_audible_bell(self.profile_settings.get_boolean(self.SETTING_KEY_PROFILE_AUDIBLE_BELL))
                except:
                    self.set_audible_bell(self.defaults['audible_bell'])
                try:
                    self.set_scroll_on_keystroke(self.profile_settings.get_boolean(self.SETTING_KEY_PROFILE_SCROLL_ON_KEYSTROKE))
                except:
                    self.set_scroll_on_keystroke(True)
                try:
                    self.set_scroll_on_output(self.profile_settings.get_boolean(self.SETTING_KEY_PROFILE_SCROLL_ON_OUTPUT))
                except:
                    self.set_scroll_on_output(True)
                
                # 滚动回滚配置
                try:
                    if self.profile_settings.get_boolean(self.SETTING_KEY_PROFILE_SCROLLBACK_UNLIMITED):
                        self.set_scrollback_lines(-1)
                    else:
                        self.set_scrollback_lines(self.profile_settings.get_int(self.SETTING_KEY_PROFILE_SCROLLBACK_LINES))
                except:
                    self.set_scrollback_lines(1000)
            else:
                # 无配置时用硬编码默认值
                self.set_audible_bell(self.defaults['audible_bell'])
                self.set_scroll_on_keystroke(True)
                self.set_scroll_on_output(True)
                self.set_scrollback_lines(1000)  # 默认滚动行数

        except Exception as e:
            print(f"[Terminal Multitab] Reconfigure VTE error: {e}", file=sys.stderr)

    def on_profile_settings_changed(self, settings, key):
        try:
            self.reconfigure_vte()
        except Exception as e:
            print(f"[Terminal Multitab] Profile settings change error: {e}", file=sys.stderr)

class GeditTerminalPanel(Gtk.Box):
    """改造为多Tab终端面板，保留原插件所有功能"""
    __gsignals__ = {
        "populate-popup": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (GObject.TYPE_OBJECT,)
        )
    }

    @debug_log
    def __init__(self):
        # 面板初始化（垂直布局）
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_border_width(2)  # 补充边框初始化

        # 快捷键配置初始化
        self._accel_base = '<gedit>/plugins/terminal_multitab'
        self._accels = {
            'copy-clipboard': [Gdk.KEY_C, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, self.copy_clipboard],
            'paste-clipboard': [Gdk.KEY_V, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, self.paste_clipboard]
        }

        # 注册快捷键（容错）
        for name in self._accels:
            try:
                path = self._accel_base + '/' + name
                if not Gtk.AccelMap.lookup_entry(path)[0]:
                    Gtk.AccelMap.add_entry(path, self._accels[name][0], self._accels[name][1])
            except Exception as e:
                print(f"[Terminal Multitab] Register accel {name} failed: {e}", file=sys.stderr)

        # ========== 多Tab核心初始化 ==========
        # 1. 创建Tab操作栏
        self._create_tab_toolbar()
        # 2. 创建Notebook多Tab容器
        self._notebook = Gtk.Notebook()
        self._notebook.set_scrollable(True)
        self._notebook.set_show_tabs(True)
        self._notebook.set_show_border(True)
        self.pack_start(self._notebook, True, True, 0)

        # 3. 默认创建第一个终端Tab
        self._terminal_count = 0
        self.create_new_terminal_tab()

    def _create_tab_toolbar(self):
        """创建Tab操作工具栏（新建/关闭按钮）"""
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        toolbar.set_margin_left(5)
        toolbar.set_margin_right(5)
        toolbar.set_margin_top(2)
        toolbar.set_margin_bottom(2)

        # 新建Tab按钮
        btn_new = Gtk.Button(label="+")
        btn_new.set_tooltip_text(_("New Terminal Tab"))
        btn_new.connect("clicked", lambda _: self.create_new_terminal_tab())
        toolbar.pack_start(btn_new, False, False, 0)

        # 关闭当前Tab按钮
        btn_close = Gtk.Button(label="-")
        btn_close.set_tooltip_text(_("Close Current Terminal Tab"))
        btn_close.connect("clicked", lambda _: self.close_current_tab())
        toolbar.pack_start(btn_close, False, False, 0)

        self.pack_start(toolbar, False, False, 0)
        toolbar.show_all()

    @debug_log
    def create_new_terminal_tab(self):
        """创建新的终端Tab（核心多Tab方法）"""
        self._terminal_count += 1
        tab_index = self._terminal_count
        print(f"[Terminal Multitab] Create new terminal tab: {tab_index}", file=sys.stdout)

        # 1. 创建终端容器（终端+滚动条）
        terminal_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        
        # 2. 创建终端实例（容错）
        try:
            vte = GeditTerminal()
            vte.show()
        except Exception as e:
            print(f"[Terminal Multitab] Create terminal failed: {e}", file=sys.stderr)
            # 降级创建基础VTE终端
            vte = Vte.Terminal()
            vte.spawn_sync(Vte.PtyFlags.DEFAULT, None, ["/bin/bash"], None, 
                          GLib.SpawnFlags.SEARCH_PATH, None, None, None)
            vte.show()
        terminal_box.pack_start(vte, True, True, 0)

        # 3. 添加滚动条
        scrollbar = Gtk.Scrollbar.new(Gtk.Orientation.VERTICAL, vte.get_vadjustment())
        scrollbar.show()
        terminal_box.pack_start(scrollbar, False, False, 0)

        # 4. 绑定终端事件
        vte.connect("child-exited", self.on_vte_child_exited, tab_index)
        vte.connect("key-press-event", self.on_vte_key_press)
        vte.connect("button-press-event", self.on_vte_button_press)
        vte.connect("popup-menu", self.on_vte_popup_menu)

        # 5. 创建Tab标签（带关闭按钮）
        tab_label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        tab_label = Gtk.Label(label=f"{_('Terminal')} {tab_index}")
        
        # ========== 修复：兼容所有Gtk 3版本的图标按钮创建 ==========
        # 步骤1：创建GtkImage对象（加载关闭图标）
        tab_close_img = Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        # 步骤2：创建空的GtkButton，再将Image添加为子组件
        tab_close_btn = Gtk.Button()
        tab_close_btn.add(tab_close_img)  # 将图标添加到按钮
        # ========== 修复结束 ==========
        
        tab_close_btn.set_size_request(20, 20)
        tab_close_btn.set_tooltip_text(_("Close Tab"))
        tab_close_btn.connect("clicked", lambda _, idx=self._notebook.get_n_pages(): self.close_tab_by_index(idx))
        
        tab_label_box.pack_start(tab_label, False, False, 0)
        tab_label_box.pack_start(tab_close_btn, False, False, 0)
        tab_label_box.show_all()

        # 6. 添加到Notebook并聚焦
        self._notebook.append_page(terminal_box, tab_label_box)
        self._notebook.set_current_page(self._notebook.get_n_pages() - 1)
        # ========== 新增：强制显示所有子组件 ==========
        terminal_box.show_all()  # 确保容器内所有组件显示
        self._notebook.show_all()  # 确保Notebook显示
        self.show_all()  # 确保面板本身显示
        vte.grab_focus()

    @debug_log
    def close_current_tab(self):
        """关闭当前激活的Tab"""
        current_idx = self._notebook.get_current_page()
        print(f"[Terminal Multitab] Close current tab: {current_idx}", file=sys.stdout)
        if current_idx >= 0:
            self.close_tab_by_index(current_idx)

    @debug_log
    def close_tab_by_index(self, idx):
        """按索引关闭Tab"""
        if idx < 0 or idx >= self._notebook.get_n_pages():
            print(f"[Terminal Multitab] Tab index {idx} out of range", file=sys.stdout)
            return
        
        # 移除并销毁Tab
        terminal_box = self._notebook.get_nth_page(idx)
        self._notebook.remove_page(idx)
        terminal_box.destroy()
        print(f"[Terminal Multitab] Tab {idx} closed, remaining tabs: {self._notebook.get_n_pages()}", file=sys.stdout)

        # 空Tab时自动新建
        if self._notebook.get_n_pages() == 0:
            print("[Terminal Multitab] No tabs left, create new one", file=sys.stdout)
            self.create_new_terminal_tab()
        else:
            # 聚焦到下一个Tab
            current_page = self._notebook.get_current_page()
            terminal_box = self._notebook.get_nth_page(current_page)
            terminal_box.get_children()[0].grab_focus()

    def get_current_terminal(self):
        """获取当前激活的终端实例"""
        current_page = self._notebook.get_current_page()
        if current_page < 0:
            return None
        terminal_box = self._notebook.get_nth_page(current_page)
        return terminal_box.get_children()[0]

    # ========== 事件处理与兼容 ==========
    def on_vte_child_exited(self, term, status, tab_index):
        """终端退出后重建Tab"""
        print(f"[Terminal Multitab] Terminal {tab_index} exited with status: {status}", file=sys.stdout)
        try:
            for idx in range(self._notebook.get_n_pages()):
                terminal_box = self._notebook.get_nth_page(idx)
                if terminal_box.get_children()[0] == term:
                    self._notebook.remove_page(idx)
                    terminal_box.destroy()
                    self.create_new_terminal_tab()
                    self._notebook.set_current_page(self._notebook.get_n_pages() - 1)
                    break
        except Exception as e:
            print(f"[Terminal Multitab] Handle terminal exit error: {e}", file=sys.stderr)

    def do_grab_focus(self):
        """聚焦到当前终端"""
        current_term = self.get_current_terminal()
        if current_term:
            current_term.grab_focus()

    def on_vte_key_press(self, term, event):
        """快捷键处理"""
        try:
            modifiers = event.state & Gtk.accelerator_get_default_mod_mask()
            # Tab切换快捷键
            if event.keyval in (Gdk.KEY_Tab, Gdk.KEY_KP_Tab, Gdk.KEY_ISO_Left_Tab):
                if modifiers == Gdk.ModifierType.CONTROL_MASK:
                    self.get_toplevel().child_focus(Gtk.DirectionType.TAB_FORWARD)
                    return True
                elif modifiers == Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK:
                    self.get_toplevel().child_focus(Gtk.DirectionType.TAB_BACKWARD)
                    return True

            # 复制粘贴快捷键
            for name in self._accels:
                path = self._accel_base + '/' + name
                entry = Gtk.AccelMap.lookup_entry(path)
                if entry and entry[0] and entry[1].accel_key == event.keyval and entry[1].accel_mods == modifiers:
                    self._accels[name][2]()
                    return True

            # 终端原生快捷键放行
            keyval_name = Gdk.keyval_name(Gdk.keyval_to_upper(event.keyval))
            if modifiers == Gdk.ModifierType.CONTROL_MASK and keyval_name in 'ACDEHKLRTUWZ':
                return False
            if modifiers == Gdk.ModifierType.MOD1_MASK and keyval_name in 'BF':
                return False

            return Gtk.accel_groups_activate(self.get_toplevel(), event.keyval, modifiers)
        except Exception as e:
            print(f"[Terminal Multitab] Key press error: {e}", file=sys.stderr)
            return False

    def on_vte_button_press(self, term, event):
        """右键菜单处理"""
        try:
            if event.button == 3:
                term.grab_focus()
                self.make_popup(event)
                return True
            return False
        except Exception as e:
            print(f"[Terminal Multitab] Button press error: {e}", file=sys.stderr)
            return False

    def on_vte_popup_menu(self, term):
        self.make_popup()

    def create_popup_menu(self):
        """创建右键菜单"""
        menu = Gtk.Menu()

        # 复制项
        item = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_COPY, None)
        item.connect("activate", lambda menu_item: self.copy_clipboard())
        item.set_accel_path(self._accel_base + '/copy-clipboard')
        current_term = self.get_current_terminal()
        item.set_sensitive(current_term and current_term.get_has_selection())
        menu.append(item)

        # 粘贴项
        item = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_PASTE, None)
        item.connect("activate", lambda menu_item: self.paste_clipboard())
        item.set_accel_path(self._accel_base + '/paste-clipboard')
        menu.append(item)

        # 自定义菜单扩展
        self.emit("populate-popup", menu)
        menu.show_all()
        return menu

    def make_popup(self, event = None):
        """显示右键菜单"""
        try:
            menu = self.create_popup_menu()
            menu.attach_to_widget(self, None)
            if event is not None:
                menu.popup_at_pointer(event)
            else:
                menu.popup_at_widget(self, Gdk.Gravity.NORTH_WEST, Gdk.Gravity.SOUTH_WEST, None)
                menu.select_first(False)
        except Exception as e:
            print(f"[Terminal Multitab] Show popup menu error: {e}", file=sys.stderr)

    def copy_clipboard(self):
        """复制到剪贴板"""
        current_term = self.get_current_terminal()
        if current_term:
            current_term.copy_clipboard()
            current_term.grab_focus()

    def paste_clipboard(self):
        """从剪贴板粘贴"""
        current_term = self.get_current_terminal()
        if current_term:
            current_term.paste_clipboard()
            current_term.grab_focus()

    def change_directory(self, path):
        """切换终端目录"""
        current_term = self.get_current_terminal()
        if current_term and path:
            try:
                path = path.replace('\\', '\\\\').replace('"', '\\"')
                current_term.feed_child(('cd "%s"\n' % path).encode('utf-8'))
                current_term.grab_focus()
            except Exception as e:
                print(f"[Terminal Multitab] Change directory error: {e}", file=sys.stderr)

class TerminalPlugin(GObject.Object, Gedit.WindowActivatable):
    """插件主类，添加完整调试日志和容错"""
    __gtype_name__ = "Terminal_Multitab_Plugin"
    window = GObject.Property(type=Gedit.Window)

    @debug_log
    def __init__(self):
        GObject.Object.__init__(self)
        self._panel = None
        print("[Terminal Multitab] Plugin initialized", file=sys.stdout)

    @debug_log
    def do_activate(self):
        """插件激活（核心入口）"""
        print(f"[Terminal Multitab] Activate plugin for window: {self.window}", file=sys.stdout)
        try:
            # 创建终端面板
            self._panel = GeditTerminalPanel()
            self._panel.connect("populate-popup", self.on_panel_populate_popup)
            self._panel.show()

            # 添加到底部面板
            bottom = self.window.get_bottom_panel()
            bottom.add_titled(self._panel, "GeditTerminalMultitabPanel", _("Terminal Multitab"))
            print("[Terminal Multitab] Panel added to bottom panel", file=sys.stdout)
        except Exception as e:
            print(f"[Terminal Multitab] Activate plugin failed: {e}", file=sys.stderr)
            raise

    @debug_log
    def do_activate(self):
        """插件激活（核心入口）"""
        print(f"[Terminal Multitab] Activate plugin for window: {self.window}", file=sys.stdout)
        try:
            # 创建终端面板
            self._panel = GeditTerminalPanel()
            self._panel.connect("populate-popup", self.on_panel_populate_popup)
            self._panel.show()

            # 添加到底部面板
            bottom = self.window.get_bottom_panel()
            bottom.add_titled(self._panel, "GeditTerminalMultitabPanel", _("Terminal Multitab"))
            # ========== 新增：强制显示底部面板 + 切换到终端标签 ==========
            bottom.set_visible(True)  # 显示底部面板
            # ========== 修复：兼容新版Gedit的Gtk.Stack面板 ==========
        
            # 切换到终端面板（兼容不同Gedit版本）
            if hasattr(bottom, 'activate_item'):
                # 老版本Gedit：使用activate_item
                bottom.activate_item(self._panel)
            elif hasattr(bottom, 'set_visible_child'):
                # 新版本Gedit（Gtk.Stack）：使用set_visible_child
                bottom.set_visible_child(self._panel)
            # ==========================================================
            print("[Terminal Multitab] Panel added to bottom panel", file=sys.stdout)
        except Exception as e:
            print(f"[Terminal Multitab] Activate plugin failed: {e}", file=sys.stderr)
            raise

    def do_update_state(self):
        pass

    def get_active_document_directory(self):
        """获取当前文档目录"""
        try:
            doc = self.window.get_active_document()
            if doc:
                location = doc.get_file().get_location()
                if location and location.has_uri_scheme("file"):
                    directory = location.get_parent()
                    return directory.get_path()
        except Exception as e:
            print(f"[Terminal Multitab] Get document directory error: {e}", file=sys.stderr)
        return None

    def on_panel_populate_popup(self, panel, menu):
        """右键菜单添加目录切换项"""
        try:
            menu.prepend(Gtk.SeparatorMenuItem())
            path = self.get_active_document_directory()
            item = Gtk.MenuItem.new_with_mnemonic(_("C_hange Directory"))
            item.connect("activate", lambda menu_item: panel.change_directory(path))
            item.set_sensitive(path is not None)
            menu.prepend(item)
        except Exception as e:
            print(f"[Terminal Multitab] Populate popup menu error: {e}", file=sys.stderr)

# ========== 插件注册（关键，修复启动错误） ==========
try:
    GObject.type_register(TerminalPlugin)
    print("[Terminal Multitab] Plugin registered successfully", file=sys.stdout)
except Exception as e:
    print(f"[Terminal Multitab] Register plugin failed: {e}", file=sys.stderr)
    raise

# 兼容旧版插件加载
def activate_plugin(plugin):
    pass

def deactivate_plugin(plugin):
    pass