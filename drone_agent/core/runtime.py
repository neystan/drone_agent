"""创建并启动 drone agent 运行时。"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from drone_agent.config.loader import load_profile
from drone_agent.logging.task_log import log_agent_message
from drone_agent.llm.client import create_llm_client
from drone_agent.llm.prompts import SYSTEM_PROMPT
from drone_agent.tools.registry import ToolContext


@dataclass(frozen=True)
class RuntimeStartResult:
    """保存 profile 解析后的运行时摘要，供测试和诊断使用。"""

    profile_name: str
    mode: str
    node_name: str
    ros_started: bool


def prepare_runtime(profile_name: str) -> RuntimeStartResult:
    """只加载并校验 profile，不启动 ROS2。"""
    profile = load_profile(profile_name)
    return RuntimeStartResult(
        profile_name=profile.name,
        mode=profile.mode,
        node_name=profile.ros.node_name,
        ros_started=False,
    )


def start_runtime(profile_name: str) -> None:
    """加载 profile 并直接启动真实 ROS2 运行时。"""
    profile = load_profile(profile_name)
    _start_live_runtime(profile)


def _start_live_runtime(profile) -> None:
    """创建 ROS2、PX4 controller 和 agent loop 的完整运行时。"""
    import rclpy
    from rclpy.executors import SingleThreadedExecutor

    from drone_agent.core.agent_loop import run_interactive_agent
    from drone_agent.px4.controller import Px4Controller

    rclpy.init()
    executor = SingleThreadedExecutor()
    controller = None
    executor_thread = None

    try:
        controller = Px4Controller(
            node_name=profile.ros.node_name,
            camera_scene_topic=profile.ros.camera_scene_topic,
        )
        executor.add_node(controller)
        executor_thread = threading.Thread(target=executor.spin, daemon=True)
        client = create_llm_client(profile)
        context = ToolContext(controller=controller, profile=profile)

        executor_thread.start()
        log_agent_message(profile, "system", SYSTEM_PROMPT)
        run_interactive_agent(client, profile.llm.model, context)
    finally:
        executor.shutdown()
        if controller is not None:
            controller.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        if executor_thread is not None:
            executor_thread.join(timeout=1.0)
