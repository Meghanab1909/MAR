"""
delivery_robot.launch.py  –  ALL-IN-ONE launch file.

Modes (set via 'mode' launch argument):
  slam       – Gazebo + SLAM + RViz (explore & build map)
  navigation – Gazebo + Nav2 + Delivery nodes + RViz (run deliveries with saved map)
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    LogInfo,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir  = get_package_share_directory("delivery_robot")
    launches = os.path.join(pkg_dir, "launch")

    # ---- Arguments ----
    mode         = LaunchConfiguration("mode",         default="slam")
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")
    map_yaml     = LaunchConfiguration(
        "map", default=os.path.join(pkg_dir, "maps", "delivery_map.yaml")
    )

    declare_mode     = DeclareLaunchArgument(
        "mode", default_value="slam",
        description="'slam' to map, 'navigation' to run deliveries",
        choices=["slam", "navigation"],
    )
    declare_sim      = DeclareLaunchArgument("use_sim_time", default_value="true")
    declare_map      = DeclareLaunchArgument(
        "map",
        default_value=os.path.join(pkg_dir, "maps", "delivery_map.yaml"),
        description="Map yaml for navigation mode",
    )

    is_slam = PythonExpression(["'", mode, "' == 'slam'"])
    is_nav  = PythonExpression(["'", mode, "' == 'navigation'"])

    # ---- Gazebo (always launched) ----
    world_path = os.path.join(pkg_dir, "worlds", "delivery_world.world")
    
    gazebo = IncludeLaunchDescription(
    	PythonLaunchDescriptionSource(os.path.join(launches, "gazebo.launch.py")),
    	launch_arguments={
		"use_sim_time": use_sim_time,
		"world": world_path,
	   }.items(),
	)

    # ---- SLAM (slam mode only) ----
    slam = GroupAction(
        condition=IfCondition(is_slam),
        actions=[
            LogInfo(msg="=== MODE: SLAM - Drive the robot to build the map ==="),
            TimerAction(
                period=3.0,
                actions=[
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            os.path.join(launches, "slam.launch.py")
                        ),
                        launch_arguments={"use_sim_time": use_sim_time}.items(),
                    )
                ],
            ),
        ],
    )

    # ---- Navigation + Delivery nodes (navigation mode only) ----
    navigation = GroupAction(
        condition=IfCondition(is_nav),
        actions=[
            LogInfo(msg="=== MODE: NAVIGATION - Running autonomous deliveries ==="),
            TimerAction(
                period=3.0,
                actions=[
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            os.path.join(launches, "navigation.launch.py")
                        ),
                        launch_arguments={
                            "use_sim_time": use_sim_time,
                            "map": map_yaml,
                        }.items(),
                    ),
                ],
            ),
            # Delivery nodes — start after Nav2 is up
            TimerAction(
                period=8.0,
                actions=[
                    Node(
                        package="delivery_robot",
                        executable="waypoint_navigator.py",
                        name="waypoint_navigator",
                        output="screen",
                        parameters=[{"use_sim_time": use_sim_time}],
                    ),
                    Node(
                        package="delivery_robot",
                        executable="delivery_manager.py",
                        name="delivery_manager",
                        output="screen",
                        parameters=[{"use_sim_time": use_sim_time}],
                    ),
                ],
            ),
        ],
    )

    # ---- RViz2 ----
    rviz = TimerAction(
        period=5.0,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(os.path.join(launches, "rviz.launch.py")),
                launch_arguments={"use_sim_time": use_sim_time}.items(),
            )
        ],
    )

    return LaunchDescription([
        declare_mode,
        declare_sim,
        declare_map,
        gazebo,
        slam,
        navigation,
        rviz,
    ])
