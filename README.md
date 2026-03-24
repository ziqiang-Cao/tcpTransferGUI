# TCP 文件传输 GUI

基于纯 TCP 的桌面文件传输工具，包含客户端与服务端 PyQt 界面，支持：

- 本地 JSON 用户管理
- 多线程分片上传与下载
- 断点续传
- 任务暂停、继续
- 客户端关闭后恢复暂停任务列表
- 服务端删除用户时可选清理用户目录
- 管理员可创建 1 天有效的临时用户，到期后自动清理账号和文件
- TLS 加密传输与服务端证书指纹信任
- PyInstaller 单文件发布
- Ubuntu `systemd` 开机自启部署
- Ubuntu `.deb` 打包
- Windows Inno Setup 安装包

## 环境

- Python 3.10-3.12
- Linux / Windows / macOS

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

说明：

- 推荐使用 Python 3.12，尤其是 Ubuntu `arm64/aarch64` 构建环境。
- `PyQt5` 在 Python 3.13 上经常没有可直接安装的预编译包，`pip` 会退回源码编译，并要求本机存在 `qmake`。
- 如果你是在 ARM Ubuntu 上构建，优先建议创建 Python 3.12 虚拟环境或 conda 环境后再安装依赖。
- ARM Ubuntu 推荐直接使用项目内置的 conda 环境文件：

```bash
conda env create -f environment.arm64.yml
conda activate tcptransgui-arm64
```

## 启动

启动服务端：

```bash
python3 Server/server_main.py
```

启动客户端：

```bash
python3 Client/client_main.py
```

## 单文件发布

项目已内置 Windows 与 Ubuntu 的单文件打包脚本，默认产出两个程序：

- `tcpTransServer`
- `tcpTransClient`

Ubuntu 构建：

```bash
bash scripts/build_ubuntu.sh
```

或者：

```bash
python3 scripts/build_release.py
```

构建结果输出到：

- `release/ubuntu/server/tcpTransServer`
- `release/ubuntu/client/tcpTransClient`
- `release/tcptransgui-server-ubuntu-<arch>-portable.tar.gz`
- `release/tcptransgui-client-ubuntu-<arch>-portable.tar.gz`
- `release/tcptransgui-server-ubuntu-portable.tar.gz`
- `release/tcptransgui-client-ubuntu-portable.tar.gz`

Windows 构建：

```bat
scripts\build_windows.bat
```

或者：

```bat
python scripts\build_release.py
```

构建结果输出到：

- `release\windows\server\tcpTransServer.exe`
- `release\windows\client\tcpTransClient.exe`
- `release\tcptransgui-server-windows-portable.zip`
- `release\tcptransgui-client-windows-portable.zip`
- `release\windows\server\install_server_autostart.bat`
- `release\windows\server\remove_server_autostart.bat`

Windows Inno Setup 安装包：

```bat
scripts\build_windows_installer.bat
```

输出目录：

- `release\windows\installer\`
- `release\windows\installer\tcpTransGUI-client-setup-<version>.exe`
- `release\windows\installer\tcpTransGUI-server-setup-<version>.exe`

说明：

- `PyInstaller` 不能在 Ubuntu 上直接产出 Windows 可执行文件，也不能在 Windows 上直接产出 Linux 可执行文件。
- 因此 Windows 版需要在 Windows 主机上执行 `build_windows.bat`。
- Ubuntu 版需要在 Ubuntu 主机上执行 `build_ubuntu.sh`。
- 单文件运行时，如果程序目录可写，`server_data/` 和 `client_data/` 会自动创建在可执行文件所在目录旁边。
- 通过 `.deb` 或安装器安装后，如果程序位于 `/opt` 等只读目录，客户端会自动改用用户目录保存数据：
  Linux 默认是 `~/.local/share/TCPTransGUI/client_data`
- 如需自定义数据目录根路径，可设置环境变量 `TCPTRANSGUI_DATA_HOME`
- 若要生成 Windows 安装程序，需要先安装 Inno Setup 6。
- 每次打包前会自动清理 `build/`、`dist/`、`release/`、`__pycache__/` 等构建中间产物。

## Ubuntu 部署

单文件构建完成后，可直接安装为 `systemd` 服务：

```bash
sudo bash release/ubuntu/install_ubuntu_server.sh
```

安装后：

- 服务名：`tcptransgui-server`
- 环境配置：`/etc/default/tcptransgui-server`
- `systemd` 用户覆盖：`/etc/systemd/system/tcptransgui-server.service.d/override.conf`
- 服务数据：默认迁移到安装用户家目录下的 `~/.local/share/TCPTransGUI/server_data`
- 桌面启动器：
  - `/usr/share/applications/tcptransgui-server.desktop`
  - `/usr/share/applications/tcptransgui-client.desktop`

常用命令：

```bash
systemctl status tcptransgui-server
sudo systemctl restart tcptransgui-server
journalctl -u tcptransgui-server -f
```

说明：

- Ubuntu `server .deb` 现在默认不会在安装后自动启动后台 `systemd` 服务。
- 直接从桌面或命令行打开 `tcptransgui-server` 时，会以 GUI 管理模式运行，并默认把数据放到当前用户目录：
  `~/.local/share/TCPTransGUI/server_data`
- 安装 `.deb` 或执行 Ubuntu 安装脚本后，后台 `systemd` 服务也会默认绑定到当前安装用户，并把数据放到该用户家目录下，避免 `/var/lib/...` 带来的权限问题。
- 服务端主界面提供了 `tcptransgui-server.service` 的启用 / 禁用开关；禁用时会同时停止后台服务，避免端口持续被占用。
- 这样可以避免“后台 headless 服务已占用端口，但 GUI 页面显示未启动”的状态分裂问题。
- 如果你确实需要无感后台常驻 / 开机自启，也可以手动执行：

```bash
sudo systemctl enable --now tcptransgui-server
```

- 若需改为其他用户家目录，可在安装前设置环境变量 `TCPTRANSGUI_SERVICE_USER=<用户名>`，或安装后修改 `/etc/default/tcptransgui-server` 与 service override 文件。

## Debian 包

在 Ubuntu 上生成 `.deb`：

```bash
bash scripts/build_deb.sh
```

输出目录：

- `release/deb/tcptransgui-client_<version>_<arch>.deb`
- `release/deb/tcptransgui-server_<version>_<arch>.deb`

说明：

- Ubuntu 单文件和 `.deb` 都是和 CPU 架构绑定的本地程序，不是跨架构通用包。
- `amd64` 机器打出来的是 `amd64` 包，只能装到 `amd64/x86_64` 机器。
- `arm64` 机器需要在 `arm64` Ubuntu 主机上重新执行打包脚本，生成 `arm64` 包后再安装。
- 若只是区分发布物，优先使用带 `<arch>` 后缀的文件名。

## 默认账号

- 用户名：`admin`
- 密码：`admin123`

## 目录说明

- `build/`
  PyInstaller 的中间构建目录，只保存分析缓存、临时打包文件和调试报告，不属于最终发布内容，可安全删除。

- `docs/PROGRAM_FLOW.md`
  客户端 / 服务端完整流程图与锁使用说明
- `docs/PROGRAM_FLOW.drawio`
  适合汇报 / 交付的 draw.io 多页面流程图源文件

- `server_data/users.json`
  服务端用户数据
- `server_data/storage/`
  服务端文件存储目录
- `client_data/state.json`
  客户端本地设置与待恢复任务

## 使用说明

1. 先启动服务端并设置监听地址与端口，默认建议使用 `9999` 这类高位端口。
2. 客户端输入 `tcp://host:port` 与账号密码登录。
3. 在客户端选择上传或下载，支持调整并发线程数。
4. 任务可暂停；关闭客户端后，下次登录同一服务器和同一账号会自动恢复任务列表。
5. 恢复出的任务默认保持暂停，点击“继续”后会从已完成分片位置继续传输。
6. 首次连接服务端时，客户端会记住服务器证书指纹；若后续证书变化，会拒绝继续连接。
7. 管理员可在服务端新增“1 天临时用户”，到期后服务端会自动删除该账号及其全部文件。
8. 客户端与服务端支持托盘常驻：点击窗口关闭按钮不会退出，只会隐藏到系统托盘；托盘右键菜单提供“重启”和“退出”。
9. 服务端 GUI 版启动后会自动驻留到系统托盘，适合无感后台运行。

## 部署建议

- 将 `server_data/` 放到稳定磁盘目录并定期备份 `users.json`
- 在局域网或公网部署时，建议结合防火墙只开放业务端口
- 如果需要开机启动，可将 `python3 Server/server_main.py --port 9999` 注册到系统服务管理器
- 发布给最终用户时，建议直接分发 `release/<platform>/` 目录
- Windows 便携版可直接运行 `install_server_autostart.bat` 创建服务端开机自启动任务
