# drone_agent 项目交接概览

最后更新：2026-11-07（Asia/Shanghai）。当前工作见 [STATUS.md](STATUS.md)，固定协作规则见 [AGENTS.md](AGENTS.md)。

## 项目目标与范围

在 Jetson Orin NX 8GB 上运行现有自然语言无人机 Agent，通过飞书文字消息接收指令、回复状态，实现低速目标跟随。目标初始化使用自然语言加 DINO-XSeek，或已有鼠标选点方式；SAM2 持续分割，深度相机测距，再驱动飞行跟随。

当前性能目标是整条 RGB、分割、有效深度观测链路稳定提供约 7–8 次更新/秒；需同时关注延迟和长尾，不能用窗口刷新或消息轮询频率代替。支持寻找、重新锁定和切换目标；目标丢失时悬停，飞书发出“保持悬停/停止”时及时停止跟随。当前不以高速跟随或复杂场景鲁棒性为验收目标。

通信端只要求文字收发，不要求图片传输；采用飞书。Jetson 优先直接使用校园网，不增加机载联网配件；日常操作目标是开机自动运行、无桌面控制，减少对 NoMachine 和 HDMI 欺骗器的依赖。

这些是用户确认的产品方向，具体控制方案和未实施事项见 STATUS.md；不表示整条链路已在 Jetson 实现或通过实机验证。

## 工作空间、仓库与资料

| 位置 | 用途与维护边界 |
| --- | --- |
| `/home/jetson/drone_agent_ws` | ROS 2 工作空间、当前 VS Code 工作目录；本身没有 Git |
| `src/drone_agent` | 本开发仓库，origin 为 `https://github.com/neystan/drone_agent.git`，当前分支 `main` |
| `src/opencv_camera_ros2` | 本地 RGB 相机发布和预览包，未纳入 Agent 的 Git 仓库 |
| `build/`、`install/`、`log/` | colcon 构建、安装和运行产物；不能仅据其存在认定与源码同步 |
| `src/drone_agent/settings.json` | 本地模型及跟踪配置，Git 忽略；支持 `DRONE_AGENT_SETTINGS` 覆盖路径 |
| `src/drone_agent/data/real/` | 真机照片、分析结果和 JSONL 日志的固定存储根；源码运行与普通安装入口保持一致 |

当前仓库入口是 `drone_agent_real` 与 `drone_agent_sim`。既有说明保留在 [README.md](README.md)、[真机迁移说明](docs/REAL_VEHICLE_MIGRATION.md)、[旧架构说明](docs/PROJECT_ARCHITECTURE.md) 和 `docs/PHASE_*.md`。旧文档中的 WSL 路径、DDS 描述或功能设想需要对照实际代码，不能直接当作当前 Jetson 事实。

维护分工参考 [drone_harness 的 REVIEW.md](https://github.com/neystan/drone_harness/blob/main/REVIEW.md) 与 [STATUS.md](https://github.com/neystan/drone_harness/blob/main/STATUS.md)，本文维护的是当前 Agent 的实机跟踪目标及本机基线。

## 初始 Git 基线与既有改动

2026-11-07 建立维护文档前，本机 `HEAD` 为 `e621606f154d655aa621763a9522c41e21c5cf1c`，提交于 2026-08-07，标题为 `require MAVROS connection for Offboard handshake`。

当时有 20 个已跟踪文件被修改，合计新增 500 行、删除 153 行，另有 `test/test_config_paths.py`、`test/test_dinoxseek_visualization.py` 两个未跟踪测试。这是本轮开始前的历史工作树快照，不包含新增维护文档；后续实际状态仍以 Git 为准。2026-11-07 待办 1 已完成与当前远端的逐文件比对，结果如下；原电脑 WSL 未提交的 RGBD 实现仍属于待办 2 的待核对内容。

初次静态核对时的改动分组如下；后续配置路径修复见下方启动与安装小节：

| 分组 | 当前工作树中的行为与来源 |
| --- | --- |
| 配置与脚本 | `config/loader.py`、`real.yaml`、两个启动包装脚本：使用项目本地 settings，相对存储路径解析到项目根，真机 RGB 为 `/camera/image_raw` |
| 起飞握手 | `px4/controller.py`、`tools/flight.py`：预热位置 setpoint，先解锁并确认，再请求并确认 OFFBOARD；增加 statustext 拒绝原因及握手等待 |
| 空地与高度 | 增加 MAVROS extended_state 空地状态；明确状态未知时拒绝依赖该状态的动作；落地未解锁且位姿有效时记录地面参考，相对移动检查距参考面至少 0.3 米 |
| 模式同步与 HITL | 定时器刷新模式/解锁确认状态；真机配置允许 `rotate`、`land` 豁免人工确认，其他相关工具按原门控处理 |
| 视觉与 skill | DINO-XSeek 在实际检测输入图保存候选框叠加图；提示词约束视觉请求的移动授权；三个 skill 文件存在启停或流程修改 |
| 既有资料与测试 | README、真机迁移说明、忽略规则及握手/状态等测试已有修改；另有上述两个未跟踪测试。待办 1 已运行现有离线测试，结果见下文 |

### 远端比对与本地保护（2026-11-07，待办 1 已完成）

待办 1 阶段在独立 bare clone 中核对远端，当时未对当前仓库执行 fetch、checkout、合并、暂存、提交或推送。远端仅有 `main`，HEAD 为 `d5fcb43754848b67a8d287e0f4b7f358e94fee60`，时间为 2026-09-03 22:12:52（北京时间），与原电脑已知提交相同。本机 `e621606` 是其祖先，远端领先两个提交，分别涉及 DINO 依赖固定和飞行安全改动；当时本机 `origin/main` 仍是旧缓存 `e621606`。

初次比对时的 20 个既有修改分类如下，保留为路径修复前的基线。随后已整合依赖声明、HITL 测试并修复配置定位，当前变化见下节；备份及临时审计文件已按用户要求删除。

| 分类 | 文件与结论 |
| --- | --- |
| 5 个逐字节与远端相同 | `config/schema.py`、`px4/controller.py`、`runtime/safety.py`、`lamp-inspection/SKILL.md`、`real-low-altitude-test/SKILL.md`；对应安全逻辑已推送 |
| 4 个只有文件末尾空白差异 | `llm/prompts.py`、`px4/status.py`、`visual-search/SKILL.md`、`tools/flight.py`；对应逻辑已推送 |
| 2 个共有安全改动并含本机部署差异 | `config/loader.py`、`config/profiles/real.yaml`；HITL 豁免已推送，本机 settings 默认位置、相对存储解析、RGB topic 和数据路径尚为 Jetson 独有 |
| 9 个 Jetson 独有的已跟踪修改 | `.gitignore`、README、真机迁移说明、DINO 检测叠加图、两个启动包装脚本、三个既有测试文件 |
| 2 个 Jetson 独有的未跟踪测试 | `test_config_paths.py`、`test_dinoxseek_visualization.py`，远端均无此文件 |

远端的 `pyproject.toml`、`setup.py` 固定 `dds-cloudapi-sdk==0.5.3`、`Flask==2.3.3` 并限定 `numpy>=1.24.4,<2`，另有 `test/test_hitl_flight_tool_exemptions.py`；这些依赖声明和测试现已整合到本地工作树，测试仅补充中文函数注释。本机已安装 DDS SDK 0.5.3、Flask 2.3.3、numpy 1.26.4、openai 1.99.9、PyYAML 6.0.2，相关模块均可导入，DINO 必需接口存在；OpenCV 4.11.0 与 numpy 的内存图片编码通过，未调用真实云服务。本次无需重新下载依赖。

初次比对时远端三个 `scripts/` 启动/预览文件缺少可执行位，本机保留的可执行属性现已随部署提交推送。远端基线未发现 RGBD 深度测距或连续速度跟随实现。前期内容整合没有推进 Git 历史；同日用户明确授权“推送”后，已 fetch 并以远端 `d5fcb43` 为提交基线，复用已有两个提交，未重复提交核心安全逻辑。

Jetson 独有内容已按以下三组审核、提交，并成功推送到 `origin/main`；同步基线前后核对的 92 个工作文件内容和权限全部一致，真实 settings 的大小、修改时间和 inode 未变：

1. `ba0f535`，部署配置与说明：`.gitignore`、README、真机迁移说明、loader、real profile、三个脚本权限及 `test_config_paths.py`。路径问题现已修复，两个包装脚本的重复环境设置已移除。
2. `2f1f427`，检测结果可视化：`vision/dinoxseek.py` 及 `test_dinoxseek_visualization.py`，同时保留视觉提示和 skill 的既有末尾空白。
3. `a9a9d09`，实机测试适配：`test_flight_safety_ack.py`、`test_mavros_controller.py`、`test_mavros_sim_runtime.py`，远端已有豁免测试补充中文说明；状态与飞行工具源码仅保留末尾空白差异。

维护规则和交接文档随当前文档提交纳入仓库。HTTPS fetch 可用，HTTPS push 因没有凭据失败后，已使用 Jetson 现有 SSH 密钥认证并完成普通推送；仅配置本仓库的提交身份及 SSH push URL，没有强制推送或改写远端既有历史。真实 settings、运行数据、模型权重和构建产物均未纳入提交，未创建新备份。

待办 1 曾创建并校验 98 个文件的本地快照及两个 Git bundle。用户随后明确要求删除该备份并在聊天中列出差异；本轮备份和临时审计副本现已删除，不再保留恢复副本或相关文件链接。现有源码、测试、配置、运行数据和 Git 历史均保留，核对结果继续在本文维护。

### 实际启动、配置与安装副本（2026-11-07）

初次核验发现：两个入口读取配置的位置不同，real 相对存储路径被解析到安装区。2026-11-07 已按用户确认的目录方案修复并通过普通 colcon 构建，再从仓库外 `/tmp` 对实际安装入口进行离线核验。探针替换 `start_runtime`，使用内存中的假模型配置检查 profile，不读取真实配置内容、不创建 ROS 节点或模型客户端。

| 项目 | 当前实际结果 |
| --- | --- |
| `drone_agent_real` / `drone_agent_sim` | 命中 `install/drone_agent/bin/` 下的包装脚本，直接调用 cli，不再修改配置环境变量 |
| `ros2 run drone_agent drone_agent_real` / sim | 解析到 `install/drone_agent/lib/drone_agent/` 下的 console script，与包装脚本共用 cli 和同一个配置加载器 |
| Python 模块 | 均从 `install/drone_agent/lib/python3.10/site-packages/drone_agent/` 导入，使用安装副本 |
| 源码与安装一致性 | 两侧全部 57 个 `.py/.yaml/.md` 文件逐字节一致，两个 bin 包装脚本也一致；当前没有旧代码差异 |
| 构建方式 | 当前是普通 build/install，没有源码符号链接；今后修改源码不会自动更新安装副本 |
| 未设置环境变量时的默认 settings | 两种入口统一为 `/home/jetson/drone_agent_ws/src/drone_agent/settings.json`，文件存在；显式路径优先于 `DRONE_AGENT_SETTINGS`，后者优先于默认值 |
| real profile 的实际存储根 | `/home/jetson/drone_agent_ws/src/drone_agent/data/real/{photos,analysis,logs}`；覆盖 settings 路径不改变数据根目录 |
| sim profile 的存储位置 | 保留原电脑绝对路径；用户已明确 Jetson 不做仿真，本次不改仿真 profile、不安装仿真环境 |

加载器新增 `_resolve_project_root`：源码布局通过 `package.xml` 定位当前仓库；普通安装复用已有 `ament_index_python.get_package_prefix`，从 colcon 安装前缀定位工作空间的 `src/drone_agent`。支持标准隔离和合并安装布局；要求保留源码目录并加载正确工作空间环境，源码缺失时明确报错。三个相对存储路径始终基于这个稳定根目录解析，绝对存储路径保持原值。

这次修复不改变飞行控制、安全限额、HITL 或视觉跟踪逻辑。真实 settings 未修改；旧 `site-packages/data/real/` 中的历史数据仍保留原位，新运行统一写入源码目录。README 与真机迁移说明已更新当前路径和普通构建操作，SAM2 持续感知从仿真 GUI 拆出的工作明确留待后续。

待办 1 的现有离线测试运行结果为 40 项通过、1 条 warning，耗时 1.60 秒。命令为 `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -p no:cacheprovider test`，从源码仓库运行并使用测试替身；warning 是系统 pytest 不识别 `pythonpath` 配置项，未修改测试环境。原输出文件已按本轮备份清理要求删除，保留此历史结果。通过结果不涵盖安装入口、真实设备或实机动作；安装路径问题由上述独立探针发现。

路径修复新增回归覆盖源码/隔离安装/合并安装、源码缺失、显式配置优先级、环境配置不改变数据根、绝对路径以及仓库外两种入口的一致性；并纳入远端两项 HITL 豁免测试。完整离线测试 49 项通过（1.61 秒），原系统 pytest 配置 warning 保留。普通 `colcon build --packages-select drone_agent --event-handlers console_direct+` 成功，1 个包完成（3.88 秒）；构建环境存在旧工作空间前缀，提示 Prometheus/cam_ros2 的 local_setup 缺失及当前包重复 underlay，这些提示未阻止本次构建，未修改用户环境。

构建后已在 `/tmp` 确认实际导入的是安装 loader，运行安装 bin 包装与 ROS console entry point 的离线探针后，两者 settings、photos、analysis、logs 完全一致；57 个包文件及两个包装脚本与源码逐字节相同，入口不再改写 `DRONE_AGENT_SETTINGS`。没有启动真实 Agent、ROS 节点、相机、模型或飞行动作。

## 当前架构与已实现能力

执行链为：本地输入终端 → `InputServer` / `MessageBus` → `runtime/agent_loop.py` 同步云模型请求 → `tool_dispatcher` → 飞行、感知、跟踪或 skill 工具 → 工具结果回到 Agent。

- [cli.py](drone_agent/cli.py) 与 [runtime.py](drone_agent/runtime/runtime.py) 负责入口和运行时；ROS executor 在后台处理 MAVROS 消息，Agent 主循环同步等待模型并顺序执行工具。
- [输入服务](drone_agent/bus/input_server.py) 目前绑定 `127.0.0.1` 随机 TCP 端口，使用临时 token；[MessageBus](drone_agent/bus/message_bus.py) 的消息只有正文和时间，没有飞书发送者或回复目的地。
- [工具注册表](drone_agent/tools/registry.py) 已包含起飞、降落、上锁、悬停、返航、旋转、相对位移、计时、状态查询、拍照、识图、检测、语义跟踪、鼠标跟踪和 skill。
- [Px4Controller](drone_agent/px4/controller.py) 通过默认 `/mavros` namespace 连接 PX4，订阅状态、位置、电池、extended_state、statustext 和 RGB；位置目标默认每 0.1 秒发布一次。内部使用 NED，相对位移为 FRD，ROS/MAVROS 侧涉及 ENU 转换。
- [飞行工具](drone_agent/tools/flight.py) 使用离散位置目标并等待动作完成，尚未形成由目标距离、方位误差持续更新的视觉跟随控制。
- [任务日志](drone_agent/logging/task_log.py) 每会话保存 `agent_messages.jsonl`、`tool_calls.jsonl`、`task_state.jsonl`。
- `drone_agent_real` 不启动 MAVROS 或相机驱动；[takeoff_camera.launch.py](launch/takeoff_camera.launch.py) 启动 AirSim 相机桥及 GUI，供仿真使用。仓库中未发现飞书接入或 systemd 自启配置。

用户历史反馈：以前已在真机通过自然语言完成起飞、降落、前进、旋转、识图和寻物。本轮只核对代码，未重新运行或验证这些实机动作。

## 相机、检测与 SAM2 的实际状态

- 工作空间 [README](../../README.md) 记录相机为 Orbbec Gemini 336L；本轮没有通过已连接设备确认型号，也未测量实际相机帧率。
- [camera_publisher.py](../opencv_camera_ros2/scripts/camera_publisher.py) 使用 OpenCV/V4L2 读取彩色帧，以 BGR8 `sensor_msgs/Image` 发布；默认请求 640×480、30 FPS。独立 publisher 默认 `/dev/video0`，相机 [launch](../opencv_camera_ros2/launch/camera_pub_sub.launch.py) 默认 `/dev/video6`，以实际启动参数为准。当前包没有深度、CameraInfo、标定及 RGBD 对齐链路。
- [real.yaml](drone_agent/config/profiles/real.yaml) 已订阅 `/camera/image_raw`；控制器只缓存 RGB，未发现目标深度测距实现。
- [DINO-XSeek](drone_agent/vision/dinoxseek.py) 通过 `dds_cloudapi_sdk` 调用云检测，输入目标文字和图像，输出候选框；当前包含保存候选框叠加图的本地修改。
- [SAM2 客户端](drone_agent/vision/sam2_client.py) 提供 `/tracking/start`、`/tracking/status`、`/tracking/stop`，用框或正样本点初始化。更新传图片路径、帧号，结果包含 mask 文件路径；服务与 Agent 必须能访问一致的图像/mask 路径。
- 当前仓库未包含 SAM2 服务实现、权重和部署脚本。本轮未确认 Jetson 是否已另行部署或运行该服务；示例 localhost:8100 和默认禁用只代表示例配置。
- [跟踪工具](drone_agent/tools/tracking.py) 已有语义初始化、多候选 `target_index`、鼠标点选和重启切换入口。鼠标路径依赖相机窗口，支持取消，最多等待 60 秒。
- 持续 SAM2 更新线程仍在 [camera_view_sim](scripts/camera_view_sim) 中，硬编码 AirSim 的 Scene RGB topic 并创建 OpenCV 窗口。topic 名称里的 `CameraDepth1` 不代表收到了深度；真机 RGB 预览没有这条 SAM2 更新线程。

## 当前实机限制与悬停边界

[real.yaml](drone_agent/config/profiles/real.yaml) 当前起飞高度上限 3 米，单轴水平相对位移上限 5 米，垂直位移 2 米，旋转 180°，动作超时 20 秒；起飞要求收到 PX4 状态、电池状态且电量至少 30%。实机 HITL 开启，`rotate`、`land` 豁免。

悬停路径需要分别看待：

| 路径 | 现有行为与限制 |
| --- | --- |
| 飞行动作超时 | [runtime/safety.py](drone_agent/runtime/safety.py) 请求悬停，等待命令响应与 AUTO.LOITER；未确认则停止 setpoint、抛出 `SafetyHandoffRequired` 并退出运行时。实际 PX4 Offboard-loss 参数和接管效果未在本轮验证 |
| 用户介入 | [bus/intervention.py](drone_agent/bus/intervention.py) 在工具边界和部分等待循环中处理消息，停止 setpoint 并发送悬停，但不确认 ACK/模式；不能打断正在同步等待的模型请求 |
| 跟踪工具查询丢失 | `tools/tracking.py` 查询状态得到 lost 才发悬停，发送后不等待飞控状态确认 |
| SAM2 持续更新丢失 | [vision/tracking.py](drone_agent/vision/tracking.py) 当前清空 mask/overlay；未连接独立的失效悬停控制，服务异常也不能视为已安全悬停 |

控制器对位置、空地状态有缓存及“曾收到”标志，本轮未发现完整的消息时效门控；不能写成已具备遥测过期保护。运行时在空中重启后可能缺少地面参考，当前相对移动会被拒绝。用户要求的飞书及时悬停、观测失效处置及失效后重新锁定仍需具体设计与验证。

## 已有联网证据

2026-11-07 在 Jetson 上直接检查：无线网卡连接 `stu-wlan`，默认路由走该无线网卡，DHCP 与校园 DNS 可用，NetworkManager 联网状态为 `full`，当时信号强度 80/100。公网网站和学校网站 HTTPS 均返回 200，飞书服务器 HTTPS 可达；没有执行机器人认证或消息收发。

Wi-Fi 已启用自动连接。重启后的校园网自动认证、飞行区域覆盖和移动过程的漫游稳定性尚未验证，当前一次联网成功不能替代这些结果。

## 原电脑 RGBD 仿真历史证据

此前在原电脑 Windows 的 Codex 附件中找到一份 AirSim RGB＋DepthPlanar 跟踪日志，时间为 2026-09-04 00:41:51–00:42:08（北京时间），共 17 条。附件标识为 `58f1bc09-c548-4d98-bd71-2c88227fadaf/pasted-text.txt`，当时位于 `C:\Users\stan\.codex-official\attachments`；本轮没有在 Jetson 上重新读取原文件。

| 历史指标 | 当时原始日志范围 |
| --- | --- |
| 相机输入 | 9.2–13.0 FPS |
| 可见更新 | 5.1–11.4 FPS |
| SAM2 worker | 7.5–10.7 FPS，另有一次会话重启归零 |
| worker 耗时滚动 P95 | 171.6–515.0 ms |
| 最大显示延迟 | 631.5 ms |

这份短日志支持当时存在低帧率和长尾卡顿；它没有完整记录有效深度观测和飞行控制更新率。此前单独 SAM2 的十几帧、桌面 GPU 的结果都不能证明 Orin NX 8GB 的整链路性能。

原电脑历史会话还记录 WSL 工程 `/home/hw/hw-ros2/ros2/src/drone_agent` 曾实现过 RGBD 观测、深度中位数测距、速度跟随和超时悬停，用户当时反馈已出现跟随效果；本次 Jetson 工作树中未发现这套实现，其现存文件和版本仍待取回核对。优先核对可复用代码，再决定本机实现范围。

## 维护初始化与基线核验

2026-11-07 已建立工作空间入口，以及仓库中的固定协作规则、项目交接概览和当前状态文档；完成对既有 Git 改动、飞控、输入、感知、跟踪和配置路径的只读盘点。

初始化文档验收通过：四份文件的入口与分工一致，36 处本地文件链接有效，无行尾空格；初始化前的 88 个已有仓库文件哈希均保持一致，原有 tracked diff 逐字节未变。仓库新增 AGENTS.md、REVIEW.md、STATUS.md，工作空间另新增入口文件；初始化阶段没有提交或推送。

随后按用户授权完成待办 1 的远端比对和 40 项离线检查，备份与临时审计副本已按用户要求删除。用户又确认路径统一、普通构建、保留共用代码及离线测试；对应 1a 已修复，依赖声明/HITL 测试内容已整合，49 项离线检查、普通构建和安装入口探针通过。最后在明确“推送”授权下完成 1b 的历史对齐、三组代码提交及普通远端推送，维护文档随当前提交更新。上述 Git 操作没有改变已验证的产品文件内容；未创建新备份、调用云模型、启动相机或执行飞行动作，也未实施其余跟踪或 channel 待办。
