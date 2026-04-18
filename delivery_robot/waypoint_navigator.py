#!/usr/bin/env python3
"""
Waypoint Navigator for Delivery Robot
Sends the robot to a sequence of delivery waypoints using Nav2 NavigateToPose action.
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup

from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose, FollowWaypoints
from action_msgs.msg import GoalStatus
from std_msgs.msg import String

import math
import time
from enum import Enum, auto


class RobotState(Enum):
    IDLE        = auto()
    NAVIGATING  = auto()
    AT_WAYPOINT = auto()
    RETURNING   = auto()
    ERROR       = auto()


DELIVERY_STATIONS = {
    "home":       ( 1.2,  0.0,  0.0),  # beyond station_C, not behind
    "station_A":  ( 0.5,  0.0,  0.0),
    "station_B":  ( 0.8,  0.0,  0.0),
    "station_C":  ( 1.0,  0.0,  0.0),
    "corridor_1": ( 0.0,  0.8,  0.0),
    "corridor_2": ( 0.0, -0.8,  0.0),
}


def yaw_to_quaternion(yaw_deg: float):
    yaw = math.radians(yaw_deg)
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def make_pose(x: float, y: float, yaw_deg: float, frame: str = "map") -> PoseStamped:
    pose = PoseStamped()
    pose.header.frame_id = frame
    pose.pose.position.x = x
    pose.pose.position.y = y
    pose.pose.position.z = 0.0

    qx, qy, qz, qw = yaw_to_quaternion(yaw_deg)
    pose.pose.orientation.x = qx
    pose.pose.orientation.y = qy
    pose.pose.orientation.z = qz
    pose.pose.orientation.w = qw
    return pose


class WaypointNavigator(Node):

    def __init__(self):
        super().__init__("waypoint_navigator")

        self._cb_group = ReentrantCallbackGroup()

        self._nav_client = ActionClient(
            self, NavigateToPose, "navigate_to_pose",
            callback_group=self._cb_group
        )

        self._wp_client = ActionClient(
            self, FollowWaypoints, "follow_waypoints",
            callback_group=self._cb_group
        )

        self._status_pub = self.create_publisher(String, "/robot_status", 10)
        self._deliv_pub  = self.create_publisher(String, "/delivery_status", 10)

        self.create_subscription(
            String,
            "/delivery_order",
            self._order_callback,
            10,
            callback_group=self._cb_group
        )

        self._state = RobotState.IDLE
        self._waypoint_queue = []
        self._current_idx = 0
        self._active_goal = None

        self.create_timer(1.0, self._publish_status)

        self.get_logger().info("WaypointNavigator ready.")

    def _order_callback(self, msg: String):
        if self._state not in (RobotState.IDLE, RobotState.ERROR):
            self.get_logger().warn(f"Busy: {self._state.name}")
            return

        station_names = [s.strip() for s in msg.data.split(",") if s.strip()]
        waypoints = []

        for name in station_names:
            if name not in DELIVERY_STATIONS:
                self.get_logger().error(f"Unknown station: {name}")
                return
            waypoints.append(name)

        if not waypoints:
            self.get_logger().warn("Empty order")
            return

        self._waypoint_queue = waypoints
        self._current_idx = 0
        self._navigate_to_next()

    def _publish_status(self):
        msg = String()
        msg.data = self._state.name
        self._status_pub.publish(msg)

    def _navigate_to_next(self):
        if self._current_idx >= len(self._waypoint_queue):
            self._publish_delivery("ALL_COMPLETE")
            self._state = RobotState.IDLE
            return

        name = self._waypoint_queue[self._current_idx]
        x, y, yaw = DELIVERY_STATIONS[name]

        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            self._state = RobotState.ERROR
            return

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = make_pose(x, y, yaw)
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()

        self._state = RobotState.NAVIGATING
        self._publish_delivery(f"NAVIGATING_TO:{name}")

        send_future = self._nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self._feedback_callback
        )
        send_future.add_done_callback(self._goal_response_callback)

    def _goal_response_callback(self, future):
        goal_handle = future.result()

        if not goal_handle.accepted:
            self._state = RobotState.ERROR
            return

        self._active_goal = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._result_callback)

    def _clear_costmaps(self):
        from nav2_msgs.srv import ClearEntireCostmap

        gc = self.create_client(
            ClearEntireCostmap,
            '/global_costmap/clear_entirely_global_costmap'
        )
        lc = self.create_client(
            ClearEntireCostmap,
            '/local_costmap/clear_entirely_local_costmap'
        )

        if gc.wait_for_service(timeout_sec=2.0):
            gc.call_async(ClearEntireCostmap.Request())

        if lc.wait_for_service(timeout_sec=2.0):
            lc.call_async(ClearEntireCostmap.Request())

        time.sleep(1.0)

    def _result_callback(self, future):
        result = future.result()
        status = result.status
        name = self._waypoint_queue[self._current_idx]

        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info(f"Arrived at: {name}")
            self._state = RobotState.AT_WAYPOINT
            self._publish_delivery(f"ARRIVED:{name}")

            self._clear_costmaps()
            time.sleep(3.0)

            self._publish_delivery(f"DELIVERED:{name}")
            self._current_idx += 1
            self._navigate_to_next()

        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().warn(f"Canceled: {name}")
            self._state = RobotState.IDLE

        else:
            self.get_logger().error(f"FAILED: {name}")
            self._state = RobotState.ERROR
            self._publish_delivery(f"FAILED:{name}")

    def _feedback_callback(self, feedback_msg):
        dist = feedback_msg.feedback.distance_remaining
        if int(dist * 10) % 5 == 0:
            self.get_logger().info(f"Distance: {dist:.2f}")

    def _publish_delivery(self, msg_str: str):
        msg = String()
        msg.data = msg_str
        self._deliv_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = WaypointNavigator()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
