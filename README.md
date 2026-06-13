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

## 模型配置

```bash
mkdir -p ~/.config/drone_agent
cp settings.example.json ~/.config/drone_agent/settings.json
```

然后在 `~/.config/drone_agent/settings.json` 里填写模型配置：

```json
{
  "llm": {
    "api_key": "your-llm-key",
    "base_url": "your-llm-base-url",
    "model": "your-llm-model"
  },
  "vlm": {
    "enabled": true,
    "api_key": "your-vlm-key",
    "base_url": "your-vlm-base-url",
    "model": "your-vlm-model"
  }
}
```

`settings.example.json` 会提交到仓库，实际运行默认读取 `~/.config/drone_agent/settings.json`。
`base_url` 和 `model` 也由你自己填写，项目不再提供 provider 默认值。
如果需要自定义位置，也可以通过环境变量 `DRONE_AGENT_SETTINGS` 覆盖默认路径。

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
