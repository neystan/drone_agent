# drone_agent

`drone_agent` 是一个使用 ROS2、MAVROS 和 PX4 的自然语言无人机控制 Agent。控制器继续使用原有路径 `drone_agent/px4/controller.py` 和类名 `Px4Controller`，不新增 `mavros/` 目录。

固定协作规则见 [AGENTS.md](AGENTS.md)，项目交接与当前工作分别见 [REVIEW.md](REVIEW.md)、[STATUS.md](STATUS.md)。

## 安装与构建

Jetson 当前 ROS2 workspace 为 `/home/jetson/drone_agent_ws`：

```bash
cd /home/jetson/drone_agent_ws
source /opt/ros/humble/setup.bash
source /home/jetson/mavros2_ws/install/setup.bash
colcon build --packages-select drone_agent
source install/setup.bash
```

使用普通构建安装；修改源码后重新构建并重启 Agent。Jetson 只进行真机开发，不要求安装或启动仿真环境。

首次运行且本地配置尚不存在时，从示例创建配置：

```bash
cp /home/jetson/drone_agent_ws/src/drone_agent/settings.example.json \
  /home/jetson/drone_agent_ws/src/drone_agent/settings.json
```

然后在 `settings.json` 中填写 LLM/VLM 的 API 配置。`drone_agent_real` 和 `ros2 run drone_agent drone_agent_real` 共用配置加载器，默认都读取源码仓库的这份文件；`DRONE_AGENT_SETTINGS` 可覆盖配置来源。

真机图片和日志固定写入 `/home/jetson/drone_agent_ws/src/drone_agent/data/real/` 下的 `photos/`、`analysis/`、`logs/`。覆盖 settings 路径不会改变数据根目录。加载器在普通安装下通过 ROS 包索引定位工作空间中的 `src/drone_agent`；源码目录应保留，入口不再自行修改环境变量。

## MAVROS 仿真流程

以下保留原电脑的仿真操作参考，Jetson 不执行这套流程。

启动 UE4/AirSim 场景后，在 WSL 中依次执行：

```bash
cd ~/PX4-Autopilot
make px4_sitl_default none_iris
```

另开终端单独启动 MAVROS：

```bash
source /opt/ros/humble/setup.bash
ros2 launch mavros px4.launch \
  fcu_url:="udp://:14540@127.0.0.1:14580" \
  tgt_system:=1 \
  tgt_component:=1
```

再开终端启动 AirSim bridge 和 RGB 相机预览：

```bash
source /opt/ros/humble/setup.bash
source ~/hw-ros2/ros2/install/setup.bash
ros2 launch drone_agent takeoff_camera.launch.py
```

该 launch 只启动 AirSim bridge 和相机预览，并订阅 AirSim RGB topic：
`/airsim_node/PX4/CameraDepth1/Scene`。不启动 MAVROS，也不再使用 `MicroXRCEAgent`。

确认 MAVROS 已连接：

```bash
ros2 topic echo /mavros/state --once
```

最后启动 Agent：

```bash
drone_agent_sim
```

也可以使用 `ros2 run drone_agent drone_agent_sim` 启动。

## 真机迁移

真机通过 MAVROS 独立连接 PX4；`drone_agent_real` 不会启动 MAVROS、相机驱动或 AirSim。
真机接入、相机 topic 配置、RTK/RC/failsafe 验收和首飞步骤见
[`docs/REAL_VEHICLE_MIGRATION.md`](docs/REAL_VEHICLE_MIGRATION.md)。

不要在真机上启动 `takeoff_camera.launch.py`，它仅用于 AirSim 仿真相机链路。

## 目录

- Python 主代码：`drone_agent/`
- ROS2 包文件：`package.xml`、`setup.py`、`launch/`
- 仿真配置：`drone_agent/config/profiles/sim.yaml`
- 真机相机 topic：`/camera/image_raw`
- 仿真相机 topic：`/airsim_node/PX4/CameraDepth1/Scene`
