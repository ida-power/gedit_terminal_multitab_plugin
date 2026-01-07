# gedit_terminal_multitab_plugin
gedit_terminal_multitab_plugin

# Gedit Terminal Multitab 插件

## 功能特性总结

### 核心功能
1. **多标签终端管理**
   - 在 gedit 底部面板嵌入多个终端标签页
   - `+` 按钮新建终端标签
   - `-` 按钮关闭当前标签
   - 标签页带独立关闭按钮
   - 自动重建：终端退出后自动创建新标签

2. **终端配置同步**
   - 自动读取 GNOME Terminal 配置（字体、颜色、调色板等）
   - 支持系统等宽字体
   - 可自定义前景色、背景色、16色调色板
   - 滚动回滚配置（滚动行数/无限制）
   - 光标闪烁模式和形状
   - 响铃设置

3. **拖拽支持**
   - 支持将文件拖拽到终端
   - 自动转换为文件路径输入

4. **快捷键**
   - `Ctrl+Shift+C` - 复制选中内容
   - `Ctrl+Shift+V` - 粘贴内容
   - `Ctrl+Tab` - 切换到下一个标签
   - `Ctrl+Shift+Tab` - 切换到上一个标签

5. **右键菜单**
   - 复制/粘贴
   - 切换到当前文档目录 (C_hange Directory)

6. **目录自动切换**
   - 右键菜单可直接切换到当前编辑文件所在目录

### 技术特性
- 基于 GTK 3 和 VTE 2.91
- 兼容 Tepl 5/6 版本
- 完善的错误处理和降级机制
- 调试日志输出（便于排查问题）
- 兼容不同版本的 gedit 面板系统

---

## 快速安装指南

### 方式一：用户级安装（推荐）

```bash
# 1. 创建插件目录（如果不存在）
mkdir -p ~/.local/share/gedit/plugins

# 2. 复制两个必需文件到插件目录
cp terminal_multitab.py ~/.local/share/gedit/plugins/
cp terminal_multitab.plugin ~/.local/share/gedit/plugins/

# 3. 重启 gedit
gedit &
```

> **注意**：两个文件都必须复制，`.plugin` 是 gedit 识别插件的配置文件

### 方式二：系统级安装

```bash
# 1. 复制两个必需文件到系统插件目录
sudo cp terminal_multitab.py /usr/lib/gedit/plugins/
sudo cp terminal_multitab.plugin /usr/lib/gedit/plugins/

# 2. 重启 gedit
gedit &
```

### 启用插件

1. 打开 gedit
2. 点击菜单：`首选项` → `插件`
3. 找到并勾选 `Terminal Multitab` 插件
4. 终端面板会自动出现在 gedit 底部

### 使用方法

| 操作 | 说明 |
|------|------|
| 显示终端 | 点击菜单 `查看` → `底部面板` 或按 `F9` |
| 新建标签 | 点击工具栏 `+` 按钮 |
| 关闭标签 | 点击标签上的 `×` 按钮或工具栏 `-` 按钮 |
| 切换标签 | 点击标签或使用 `Ctrl+Tab` |
| 切换目录 | 右键终端 → `C_hange Directory` |

### 依赖要求

```bash
# Ubuntu/Debian
sudo apt install gedit gedit-plugins libgtk-3-dev libvte-2.91-dev

# Fedora/RHEL
sudo dnf install gedit gedit-plugins gtk3-devel vte291-devel

# Arch Linux
sudo pacman -S gedit gedit-plugins gtk3 vte3
```

### 故障排查

如果插件无法加载，可查看日志：

```bash
# 查看终端日志
journalctl /usr/bin/gedit -f

# 或直接运行 gedit 查看控制台输出
gedit 2>&1 | grep -i terminal
```

常见问题：
- **黑屏/无响应**：检查 VTE 版本是否为 2.91+
- **配置不生效**：确保已安装 GNOME Terminal
- **插件未显示**：确认文件权限为可执行

---

## 文件信息

- **插件名称**: Terminal Multitab
- **插件文件**: `terminal_multitab.py`
- **Gedit 版本**: 3.0+
- **依赖**: GTK 3.0, VTE 2.91, Gedit 3.0

![gedit_terminal_multitab_plugin](https://github.com/ida-power/gedit_terminal_multitab_plugin/blob/main/2026-01-07_13-38-19.png?raw=true)

![gedit_terminal_multitab_plugin](https://github.com/ida-power/gedit_terminal_multitab_plugin/blob/main/2026-01-07_13-30-56.png?raw=true)
