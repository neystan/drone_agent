import os
import launch
import launch_ros.actions
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory 
from launch.actions import ExecuteProcess

def generate_launch_description():
    depth_camera_relay_node = Node(
        package='topic_tools',        # 节点所属的包
        executable='relay',           # 可执行文件名称（对应 ros2 run 的 relay）
        name='depth_camera_relay',    # 节点名称（可选，避免与其他节点重名）
        arguments=[
            '/airsim_node/PX4/CameraDepth/DepthPerspective/camera_info', # 源话题（第一个参数）
            '/airsim_node/PX4/CameraDepth/camera_info'                   # 目标话题（第二个参数）
        ],
        output='screen'               # 日志输出到终端（方便调试）
    )

    image_camera_relay_node = Node(
        package='topic_tools',        # 节点所属的包
        executable='relay',           # 可执行文件名称（对应 ros2 run 的 relay）
        name='image_camera_relay',    # 节点名称（可选，避免与其他节点重名）
        arguments=[
            '/airsim_node/PX4/CameraImage/Scene/camera_info',  # 源话题（第一个参数）
            '/airsim_node/PX4/CameraImage/camera_info'         # 目标话题（第二个参数）
        ],
        output='screen'               # 日志输出到终端（方便调试）
    )

    hw_move_velocity_node = Node(
            package='drone_agent',
            executable='move_velocity',
            name='move_velocity',
            output='screen')

    pkg_share = get_package_share_directory('drone_agent')
    depth_rviz_path = os.path.join(pkg_share, 'rviz/depth_cloud.rviz')
    image_lidar_rviz_path = os.path.join(pkg_share, 'rviz/image_lidar.rviz')

    hw_rviz_depth_node = launch_ros.actions.Node(
            package='rviz2',
            executable='rviz2',
            name='depth_rviz2',
            arguments=['-d', depth_rviz_path]
    )

    hw_rviz_image_lidar_node = launch_ros.actions.Node(
            package='rviz2',
            executable='rviz2',
            name='image_lidar_rviz2',
            arguments=['-d', image_lidar_rviz_path]
    )

    airsim_node_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('airsim_ros_pkgs'), 'launch/airsim_node.launch.py')
        )
    )
    # Create the launch description and populate
    ld = LaunchDescription()
    ld.add_action(airsim_node_launch)
    ld.add_action(hw_move_velocity_node)
    ld.add_action(depth_camera_relay_node)
    ld.add_action(image_camera_relay_node)
    ld.add_action(hw_rviz_depth_node)
    ld.add_action(hw_rviz_image_lidar_node)
    return ld
