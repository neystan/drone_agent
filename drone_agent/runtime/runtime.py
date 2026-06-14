"""创建并启动 drone agent 运行时。"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from drone_agent.config.loader import load_profile
from drone_agent.logging.task_log import create_session_id, log_agent_message
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

    from drone_agent.runtime.agent_loop import agent_loop
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
        context = ToolContext(controller=controller, profile=profile, session_id=create_session_id())
        executor_thread.start()
        log_agent_message(profile, context.session_id, "system", SYSTEM_PROMPT)
        _run_interactive_loop(client, profile.llm.model, context, agent_loop)
    finally:
        executor.shutdown()
        if controller is not None:
            controller.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        if executor_thread is not None:
            executor_thread.join(timeout=1.0)


def _configure_readline() -> None:
    """配置终端输入行为，避免中文编辑异常。"""
    try:
        import readline
    except ImportError:
        return

    readline.parse_and_bind("set bind-tty-special-chars off")
    readline.parse_and_bind("set input-meta on")
    readline.parse_and_bind("set output-meta on")
    readline.parse_and_bind("set convert-meta off")


def _run_interactive_loop(client: Any, model: str, context: ToolContext, agent_loop: Any) -> None:
    """运行命令行交互循环，并把每轮输入交给 agent loop。"""
    _configure_readline()
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("输入自然语言与 agent 对话，输入 exit 退出。")

    while True:
        user_input = input("you> ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break
        messages.append({"role": "user", "content": user_input})
        log_agent_message(context.profile, context.session_id, "user", user_input)
        agent_loop(client, model, messages, context)
