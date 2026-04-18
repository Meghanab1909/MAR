"""
gazebo.launch.py  –  Spawns the delivery robot in the warehouse Gazebo world.
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("delivery_robot")
    pkg_gazebo_ros = get_package_share_directory("gazebo_ros")

    # ---- Launch arguments ----
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")
    x_pose      = LaunchConfiguration("x_pose",      default="0.0")
    y_pose      = LaunchConfiguration("y_pose",      default="0.0")
    world_file  = LaunchConfiguration(
        "world",
        default=os.path.join(pkg_dir, "worlds", "delivery_world.world"),
    )

    declare_use_sim_time = DeclareLaunchArgument(
        "use_sim_time", default_value="true",
        description="Use simulation (Gazebo) clock if true",
    )
    declare_x_pose = DeclareLaunchArgument(
        "x_pose", default_value="0.0",
        description="Initial x position of robot",
    )
    declare_y_pose = DeclareLaunchArgument(
        "y_pose", default_value="0.0",
        description="Initial y position of robot",
    )
    declare_world = DeclareLaunchArgument(
        "world",
        default_value=os.path.join(pkg_dir, "worlds", "delivery_world.world"),
        description="Path to Gazebo world file",
    )

    # ---- Robot description from URDF ----
    urdf_file = os.path.join(pkg_dir, "urdf", "delivery_robot.urdf.xacro")
    robot_description = Command(["xacro ", urdf_file])

    # ---- Gazebo server & client ----
    gzserver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, "launch", "gzserver.launch.py")
        ),
        launch_arguments={"world": world_file, "verbose": "false"}.items(),
    )
    gzclient = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, "launch", "gzclient.launch.py")
        ),
    )

    # ---- Robot State Publisher ----
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time, "robot_description": robot_description}
        ],
    )

    # ---- Spawn robot in Gazebo ----
    spawn_entity = Node(
        package="gazebo_ros",
        executable="spawn_entity.py",
        name="spawn_delivery_robot",
        arguments=[
            "-topic", "robot_description",
            "-entity", "delivery_robot",
            "-x", x_pose,
            "-y", y_pose,
            "-z", "0.1",
        ],
        output="screen",
    )

    return LaunchDescription([
        SetEnvironmentVariable("RCUTILS_LOGGING_BUFFERED_STREAM", "1"),
        declare_use_sim_time,
        declare_x_pose,
        declare_y_pose,
        declare_world,
        gzserver,
        gzclient,
        robot_state_publisher,
        spawn_entity,
    ])
