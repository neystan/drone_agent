# drone_agent

`drone_agent` 是一个自然语言无人机控制 Agent。当前项目主线基于 ROS2 `rclpy`、`px4_msgs` 和 PX4 uXRCE-DDS。

## 安装

```bash
cd /download/drone_agent
python3 -m pip install -e .[dev]
```

## 环境变量

```bash
export DRONE_AGENT_LLM_API_KEY="your-llm-key"
export DRONE_AGENT_VLM_API_KEY="your-vlm-key"
```

API key 不能写入源码。

## 启动

```bash
drone_agent_sim
drone_agent_real
```

这些命令都会直接启动程序并进入交互式运行模式。运行前需要本机已有 ROS2、`px4_msgs`、PX4 DDS 链路和相机 topic。

## 验收顺序

仿真建议顺序：

```bash
drone_agent_sim
```

真机建议顺序：

1. `查询状态`
2. `查询电池`
3. 低高度起飞
4. `hover`
5. `land`
