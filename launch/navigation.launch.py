"""
navigation.launch.py  –  Launches Nav2 stack with a pre-built map (AMCL localization).
Run this AFTER gazebo.launch.py when you have a saved map.
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir    = get_package_share_directory("delivery_robot")
    pkg_nav2   = get_package_share_directory("nav2_bringup")

    # ---- Launch arguments ----
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")
    map_yaml     = LaunchConfiguration(
        "map",
        default=os.path.join(pkg_dir, "maps", "delivery_map.yaml"),
    )
    nav2_params = os.path.join(pkg_dir, "config", "nav2_params.yaml")
    autostart    = LaunchConfiguration("autostart", default="true")

    declare_sim   = DeclareLaunchArgument(
        "use_sim_time", default_value="true",
        description="Use simulation clock",
    )
    declare_map   = DeclareLaunchArgument(
        "map",
        default_value=os.path.join(pkg_dir, "maps", "delivery_map.yaml"),
        description="Full path to map yaml file",
    )
    declare_params = DeclareLaunchArgument(
        "params_file",
        default_value=os.path.join(pkg_dir, "config", "nav2_params.yaml"),
        description="Nav2 parameters file",
    )
    declare_auto  = DeclareLaunchArgument(
        "autostart", default_value="true",
        description="Automatically startup the nav2 stack",
    )

    # ---- Nav2 bringup ----
    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_nav2, "launch", "bringup_launch.py")
        ),
        launch_arguments={
            "map":          map_yaml,
            "use_sim_time": use_sim_time,
            "params_file":  nav2_params,
            "autostart":    autostart,
        }.items(),
    )

    return LaunchDescription([
        declare_sim,
        declare_map,
        declare_params,
        declare_auto,
        nav2,
    ])
