# TCPTransGUI 程序流程图

本文档给出客户端、服务端的完整运行流程，并补充线程模型、锁的使用说明与并发边界。

## 1. 总体结构

```mermaid
flowchart LR
    subgraph Client["客户端进程"]
        CM["client_main.py"]
        LD["LoginDialog"]
        MW["MainWindow"]
        FC["FileTransferClient"]
        TT["TransferTask(QThread)"]
        CS["ClientStateStore"]
    end

    subgraph Common["公共层"]
        PR["common.protocol\nJSON + 分片流"]
        SEC["common.security\nTLS / 指纹"]
        TRAY["common.tray\n托盘控制"]
    end

    subgraph Server["服务端进程"]
        SM["server_main.py"]
        SD["ServerDashboard"]
        TS["TransferServer"]
        US["UserStore"]
        FS["FileStorage"]
        SS["ServerSettingsStore"]
    end

    CM --> LD
    LD --> FC
    CM --> MW
    MW --> TT
    MW --> CS
    FC --> PR
    PR --> SEC
    PR --> TS

    SM --> SD
    SD --> TS
    SD --> SS
    TS --> US
    TS --> FS
    SD --> TRAY
    MW --> TRAY
```

## 2. 客户端主流程

```mermaid
flowchart TD
    A["启动 Client/client_main.py"] --> B["创建 QApplication"]
    B --> C["加载图标 / 初始化 client_data"]
    C --> D["ClientStateStore.load_settings()"]
    D --> E["创建 FileTransferClient"]
    E --> F["弹出 LoginDialog"]
    F --> G{"用户点击登录?"}
    G -- 否 --> Z["进程结束"]
    G -- 是 --> H["FileTransferClient.login()"]
    H --> I["open_connection(host, port)"]
    I --> J["TLS 握手 + 证书指纹检查"]
    J --> K["发送 action=login"]
    K --> L{"服务端认证成功?"}
    L -- 否 --> M["登录框显示错误"]
    M --> F
    L -- 是 --> N["保存 last_server / thread_count"]
    N --> O["创建 MainWindow"]
    O --> P["restore_saved_tasks() 恢复任务列表"]
    P --> Q["refresh_files() 拉取远端文件列表"]
    Q --> R["创建托盘图标"]
    R --> S["进入 Qt 事件循环"]

    S --> T{"用户操作"}
    T -- 浏览文件 --> U["list_files / create_folder / rename / move / delete"]
    T -- 上传 --> V["add_task_entry() -> start_task(upload)"]
    T -- 下载 --> W["add_task_entry() -> start_task(download)"]
    T -- 暂停/继续 --> X["toggle_task_pause()"]
    T -- 关闭窗口 --> Y["隐藏到托盘并持久化任务"]
    U --> S
    V --> S
    W --> S
    X --> S
    Y --> S
```

## 3. 客户端传输任务流程

### 3.1 上传 / 下载任务统一流程

```mermaid
flowchart TD
    A["MainWindow.start_task(entry, resumed)"] --> B["build_task() 创建 TransferTask"]
    B --> C["连接 progress/status/completed 信号"]
    C --> D["QThread.start()"]
    D --> E["TransferTask.run()"]
    E --> F{"mode"}

    F -- upload --> G["status=准备上传"]
    G --> H["prepare_upload() 获取 total_chunks / uploaded_chunks"]
    H --> I["根据 uploaded_chunks 计算待传分片"]
    I --> J["ThreadPoolExecutor 并发提交 _upload_chunk"]

    F -- download --> K["status=准备下载"]
    K --> L["prepare_download() 获取 total_chunks"]
    L --> M["扫描 .parts 缓存目录，识别已完成分片"]
    M --> N["ThreadPoolExecutor 并发提交 _download_chunk"]

    J --> O["每个分片线程独立建立 TLS 连接"]
    N --> O
    O --> P["分片传输时调用 _report_progress()"]
    P --> Q["发射 progress_changed / speed_changed"]
    Q --> R["MainWindow 更新卡片 UI 并 persist_tasks()"]

    J --> S{"全部上传分片成功?"}
    N --> T{"全部下载分片成功?"}
    S -- 是 --> U["服务端合并分片完成"]
    T -- 是 --> V["客户端合并 .part 到最终文件"]
    U --> W["status=已完成"]
    V --> W
    W --> X["completed(True, 传输完成)"]

    S -- 否 --> Y["异常或中断"]
    T -- 否 --> Y
    Y --> Z{"原因"}
    Z -- __paused__ --> AA["status=已暂停，保留任务"]
    Z -- __stopped__ --> AB["静默停止"]
    Z -- 其他异常 --> AC["status=失败，显示错误"]
```

### 3.2 暂停 / 恢复 / 关闭恢复

```mermaid
flowchart TD
    A["用户点击暂停"] --> B["TransferTask.pause()"]
    B --> C["_paused=True"]
    C --> D["_stop_requested.set()"]
    D --> E["工作线程在 _check_interrupted() 抛出 __paused__"]
    E --> F["MainWindow.finish_task() 标记为已暂停"]
    F --> G["persist_tasks(force=True) 写入 state.json"]

    H["用户点击继续"] --> I["MainWindow.start_task(entry, resumed=True)"]
    I --> J["重新 build_task()"]
    J --> K["上传: prepare_upload() 读取已传分片"]
    J --> L["下载: 扫描 .parts 目录"]
    K --> M["仅补传缺失分片"]
    L --> N["仅补下缺失分片"]

    O["用户关闭客户端"] --> P["closeEvent()"]
    P --> Q["对每个运行中任务执行 pause() + wait(2000)"]
    Q --> R["persist_tasks(for_shutdown=True)"]
    R --> S["托盘常驻或真正退出"]
    S --> T["下次启动 restore_saved_tasks()"]
```

## 4. 服务端主流程

```mermaid
flowchart TD
    A["启动 Server/server_main.py"] --> B["解析参数 --headless/--host/--port"]
    B --> C["resolve_data_dir()"]
    C --> D["build_server()"]
    D --> E["创建 UserStore / FileStorage / TLS 证书上下文"]
    E --> F["创建 ServerSettingsStore"]
    F --> G{"headless ?"}
    G -- 是 --> H["run_headless()"]
    G -- 否 --> I["检测 DISPLAY/WAYLAND"]
    I --> J{"GUI 可用?"}
    J -- 否 --> H
    J -- 是 --> K["创建 QApplication"]
    K --> L["创建 ServerDashboard"]
    L --> M["若 auto_start_service 为真则 start_server()"]
    M --> N["创建托盘图标，默认隐藏到托盘"]
    N --> O["进入 Qt 事件循环"]

    H --> P["server.start(host, port)"]
    P --> Q["创建监听 socket"]
    Q --> R["启动 accept_thread + maintenance_thread"]
    R --> S["进入事件循环 / 信号等待"]
```

## 5. 服务端请求处理流程

```mermaid
flowchart TD
    A["accept_thread.accept()"] --> B["TLS wrap_socket(server_side=True)"]
    B --> C["为该连接创建独立 handler 线程"]
    C --> D["_handle_connection()"]
    D --> E["recv_message() 读取 action"]
    E --> F{"action 类型"}

    F -- login --> G["_handle_login()"]
    F -- 文件浏览/改名/移动/删除 --> H["校验 session -> 调用 FileStorage"]
    F -- prepare_upload --> I["FileStorage.prepare_upload()"]
    F -- upload_chunk --> J["FileStorage.write_upload_chunk()"]
    F -- prepare_download --> K["FileStorage.prepare_download()"]
    F -- download_chunk --> L["send payload_size -> FileStorage.stream_download_chunk()"]
    F -- 用户管理 --> M["校验 admin -> 调用 UserStore / FileStorage"]

    G --> N["生成 token，写入 _sessions"]
    H --> O["send_message(status=ok)"]
    I --> O
    J --> P["统计 upload_bytes，必要时合并分片"]
    K --> O
    L --> Q["统计 download_bytes"]
    M --> O
    N --> O

    D --> R{"发生异常?"}
    R -- 是 --> S["send_message(status=error)"]
    S --> T["写日志"]
    R -- 否 --> U["连接关闭"]
```

## 6. 锁与并发模型说明

### 6.1 客户端锁

| 位置 | 类型 | 保护对象 | 何时加锁 | 说明 |
|---|---|---|---|---|
| `ClientStateStore._lock` | `threading.RLock` | `state.json` 对应的内存状态 `_state` | `load_settings/save_settings/load_tasks/save_tasks/load_server_fingerprint/save_server_fingerprint` | 防止 UI 线程与任务回调同时读写客户端状态文件。使用 `RLock` 是因为 `save_settings()` 内部会再次调用 `load_settings()`。 |
| `TransferTask._progress_lock` | `threading.Lock` | `completed_bytes`、`_last_emit`、瞬时速度计算 | 多个分片线程同时回报进度时 | 上传/下载使用 `ThreadPoolExecutor` 并发分片，没有这把锁会导致进度、速度重复累计或跳变。 |
| `TransferTask._stop_requested` | `threading.Event` | 暂停/停止标记 | `pause()/stop()/run()` 期间 | 这不是锁，但承担跨线程中断协调职责。工作线程会在 `_check_interrupted()` 中读取。 |

### 6.2 服务端锁

| 位置 | 类型 | 保护对象 | 何时加锁 | 说明 |
|---|---|---|---|---|
| `TransferServer._state_lock` | `threading.RLock` | `_running`、`_server_socket`、`_sessions`、`_stats` | `start/stop/is_running/current_stats/_handle_login/_require_session/_bump_stat/_emit_sessions/update_user/purge_expired_users` | 服务端存在 accept 线程、maintenance 线程、多个连接处理线程和 GUI 线程，所有运行态共享状态都由这把锁保护。 |
| `UserStore.lock` | `threading.RLock` | `_data["users"]` 与 `users.json` | 用户查询、登录校验、增删改、到期清理 | 防止管理员操作、登录线程、维护线程同时修改用户数据。使用 `RLock` 便于内部嵌套调用。 |
| `ServerSettingsStore._lock` | `threading.RLock` | `_settings` 与 `settings.json` | GUI 改 host/port/auto_start 时 | 保护服务端设置持久化，避免界面多个信号连续触发时写坏配置。 |
| `FileStorage._locks[username:upload_id]` | `threading.Lock` | 单个上传会话的分片合并阶段 | `write_upload_chunk()` 检查“所有分片是否齐全”并 `_merge_chunks()` 时 | 分片上传是并发的，多条上传线程可能几乎同时写完最后几个分片；这把锁保证同一 `upload_id` 只会触发一次合并。 |

### 6.3 哪些地方没有显式锁

- `MainWindow` 大部分状态更新没有显式锁，因为 Qt Widget 只能在 GUI 主线程操作。
- `FileStorage` 的普通文件列表、目录创建、重命名、移动、删除没有额外全局锁，依赖操作系统文件系统原子性与“单个请求单线程处理”模型。
- `common.protocol` 与 `common.security` 没有共享可变状态，因此不需要锁。

## 7. 关键并发边界

### 7.1 客户端

1. `MainWindow` 运行在 Qt 主线程。
2. 每个 `TransferTask` 是一个 `QThread`。
3. 每个 `TransferTask` 内部又会创建 `ThreadPoolExecutor`，并发处理多个分片。
4. 分片线程不直接操作 UI，只通过 `pyqtSignal` 回到主线程更新界面。

### 7.2 服务端

1. 主监听线程负责 `accept()`。
2. 每个 TCP 连接会派生一个处理线程。
3. 后台 `maintenance_thread` 每 60 秒清理一次过期临时用户。
4. 若存在 GUI，`ServerDashboard` 通过 Qt 信号接收运行状态变更。

## 8. 一次完整上传的时序图

```mermaid
sequenceDiagram
    participant UI as Client MainWindow
    participant Task as TransferTask
    participant Pool as Chunk Worker
    participant Proto as TLS/Protocol
    participant TS as TransferServer
    participant FS as FileStorage

    UI->>Task: start_task(upload)
    Task->>TS: prepare_upload
    TS->>FS: prepare_upload
    FS-->>TS: total_chunks + uploaded_chunks
    TS-->>Task: 续传计划

    loop 每个待传分片
        Task->>Pool: submit(_upload_chunk)
        Pool->>TS: upload_chunk + payload
        TS->>FS: write_upload_chunk
        FS->>FS: 写入 .part
        FS->>FS: 对 username:upload_id 加锁检查是否齐片
        alt 最后一个缺失分片到达
            FS->>FS: _merge_chunks()
        end
        FS-->>TS: complete?
        TS-->>Pool: status=ok
        Pool-->>Task: progress callback
    end

    Task-->>UI: progress_changed/status_changed/completed
    UI->>UI: persist_tasks() / refresh_files()
```

## 9. 一次完整下载的时序图

```mermaid
sequenceDiagram
    participant UI as Client MainWindow
    participant Task as TransferTask
    participant Pool as Chunk Worker
    participant TS as TransferServer
    participant FS as FileStorage

    UI->>Task: start_task(download)
    Task->>TS: prepare_download
    TS->>FS: prepare_download
    FS-->>TS: total_chunks
    TS-->>Task: 下载计划

    Task->>Task: 扫描 .parts 目录恢复已完成分片

    loop 每个待下载分片
        Task->>Pool: submit(_download_chunk)
        Pool->>TS: download_chunk
        TS->>FS: prepare_download / stream_download_chunk
        TS-->>Pool: payload_size + chunk bytes
        Pool->>Pool: 写入 chunk.part.tmp -> rename 成 .part
        Pool-->>Task: progress callback
    end

    Task->>Task: 按序合并 .part -> .downloading -> 最终文件
    Task-->>UI: completed(True)
```

## 10. 阅读建议

若要沿代码继续跟踪，建议按这个顺序看：

1. 客户端入口：`Client/client_main.py`
2. 客户端主窗：`Client/src/ui/main_window.py`
3. 传输线程：`Client/src/core/transfer.py`
4. 服务端入口：`Server/server_main.py`
5. 服务端核心：`Server/src/core/server.py`
6. 用户与文件层：`Server/src/core/auth.py`、`Server/src/core/file_manager.py`
7. 状态持久化：`Client/src/core/state_store.py`、`Server/src/core/settings_store.py`
