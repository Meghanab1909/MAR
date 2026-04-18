"""
slam.launch.py  –  Launches SLAM Toolbox in online async mapping mode.
Run this AFTER gazebo.launch.py to build the map.
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir       = get_package_share_directory("delivery_robot")
    pkg_slam      = get_package_share_directory("slam_toolbox")

    use_sim_time  = LaunchConfiguration("use_sim_time", default="true")
    slam_params   = LaunchConfiguration(
        "slam_params_file",
        default=os.path.join(pkg_dir, "config", "slam_toolbox_params.yaml"),
    )

    declare_sim   = DeclareLaunchArgument(
        "use_sim_time", default_value="true",
        description="Use simulation clock",
    )
    declare_params = DeclareLaunchArgument(
        "slam_params_file",
        default_value=os.path.join(pkg_dir, "config", "slam_toolbox_params.yaml"),
        description="SLAM Toolbox params file",
    )

    # SLAM Toolbox – online async mapper
    slam_toolbox = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_slam, "launch", "online_async_launch.py")
        ),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "slam_params_file": slam_params,
        }.items(),
    )

    return LaunchDescription([
        declare_sim,
        declare_params,
        slam_toolbox,
    ])
