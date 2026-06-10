# drone_agent

`drone_agent` 是一个自然语言无人机控制 Agent。当前项目主线基于 ROS2 `rclpy`、`px4_msgs` 和 PX4 uXRCE-DDS。

这个目录现在同时承担两个角色：

- GitHub 主仓
- ROS2 `ament_python` 包源码目录

如果你要放进 ROS2 workspace，最终只保留这一个目录即可。

## 目录定位

- Python 主代码：`drone_agent/`
- ROS2 包壳：`package.xml`、`setup.py`、`setup.cfg`、`resource/`
- 旧设计文档归档：`docs/legacy_specs/`

## 环境变量

```bash
export DRONE_AGENT_LLM_API_KEY="your-llm-key"
export DRONE_AGENT_VLM_API_KEY="your-vlm-key"
```

API key 不建议写入源码仓库。

## 作为 ROS2 包使用

假设你的 workspace 是 `~/hw-ros2/ros2`：

```bash
cd ~/hw-ros2/ros2/src
ln -s /download/drone_agent drone_agent

cd ~/hw-ros2/ros2
colcon build --packages-select drone_agent
source install/setup.bash
```

启动：

```bash
drone_agent_sim
drone_agent_real
```

也可以使用 ROS2 方式启动：

```bash
ros2 run drone_agent drone_agent_sim
ros2 run drone_agent drone_agent_real
```

## 作为独立 Python 项目使用

```bash
cd /download/drone_agent
python3 -m pip install -e .[dev]
```

## 运行前提

运行前需要本机已有：

- ROS2
- `px4_msgs`
- PX4 DDS 链路
- 相机 topic

仿真模式默认读取 `drone_agent/config/profiles/sim.yaml` 中的相机 topic。

## 验收顺序

仿真建议先执行：

```bash
drone_agent_sim
```

真机建议顺序：

1. `查询状态`
2. `查询电池`
3. 低高度起飞
4. `hover`
5. `land`
