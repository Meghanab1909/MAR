#!/usr/bin/env python3
"""
Delivery Manager for Autonomous Delivery Robot
High-level mission coordinator: manages delivery queue, tracks status,
and orchestrates the full A→B→C→Home delivery cycle.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
import json
import time
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum, auto


class MissionStatus(Enum):
    PENDING    = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE   = "COMPLETE"
    FAILED     = "FAILED"


@dataclass
class DeliveryMission:
    mission_id: str
    destinations: List[str]
    priority: int = 1
    status: MissionStatus = MissionStatus.PENDING
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self):
        return {
            "mission_id":   self.mission_id,
            "destinations": self.destinations,
            "priority":     self.priority,
            "status":       self.status.value,
            "created_at":   self.created_at,
            "completed_at": self.completed_at,
        }


class DeliveryManager(Node):
    """
    High-level delivery mission manager.

    Subscribes:
        /delivery_status  (std_msgs/String) - updates from waypoint_navigator
        /new_mission      (std_msgs/String) - JSON mission from operator/UI

    Publishes:
        /delivery_order   (std_msgs/String) - commands to waypoint_navigator
        /mission_report   (std_msgs/String) - JSON mission log

    JSON mission format (publish to /new_mission):
        {
          "mission_id": "M001",
          "destinations": ["station_A", "station_B", "home"],
          "priority": 1
        }
    """

    def __init__(self):
        super().__init__("delivery_manager")

        # ---- Publishers ----
        self._order_pub  = self.create_publisher(String, "/delivery_order",  10)
        self._report_pub = self.create_publisher(String, "/mission_report",  10)

        # ---- Subscribers ----
        self.create_subscription(String, "/delivery_status", self._status_callback, 10)
        self.create_subscription(String, "/new_mission",     self._mission_callback, 10)
        self.create_subscription(String, "/robot_status",    self._robot_status_cb,  10)

        # ---- State ----
        self._mission_queue: List[DeliveryMission] = []
        self._active_mission: Optional[DeliveryMission] = None
        self._robot_state  = "IDLE"
        self._mission_counter = 0

        # ---- Timers ----
        self.create_timer(2.0, self._process_queue)
        self.create_timer(5.0, self._publish_report)

        # ---- Pre-load demo missions ----
        self._load_demo_missions()

        self.get_logger().info(
            "DeliveryManager ready.\n"
            "  Send missions to /new_mission as JSON.\n"
            "  Monitor /mission_report for status."
        )

    # ------------------------------------------------------------------
    # Demo missions
    # ------------------------------------------------------------------

    def _load_demo_missions(self):
        """Queue a sample delivery route on startup."""
        demo = DeliveryMission(
            mission_id="DEMO_001",
            destinations=["station_A", "station_B", "station_C", "home"],
            priority=1,
        )
        self._mission_queue.append(demo)
        self.get_logger().info(f"Demo mission queued: {demo.mission_id} → {demo.destinations}")

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _mission_callback(self, msg: String):
        """Parse JSON mission and add to queue."""
        try:
            data = json.loads(msg.data)
            mission = DeliveryMission(
                mission_id   = data.get("mission_id", f"M{self._mission_counter:04d}"),
                destinations = data["destinations"],
                priority     = data.get("priority", 1),
            )
            self._mission_counter += 1
            # Insert by priority (higher first)
            inserted = False
            for i, m in enumerate(self._mission_queue):
                if mission.priority > m.priority:
                    self._mission_queue.insert(i, mission)
                    inserted = True
                    break
            if not inserted:
                self._mission_queue.append(mission)

            self.get_logger().info(
                f"Mission added: {mission.mission_id} | "
                f"dest={mission.destinations} | priority={mission.priority}"
            )
        except (json.JSONDecodeError, KeyError) as e:
            self.get_logger().error(f"Invalid mission JSON: {e}\nReceived: {msg.data}")

    def _status_callback(self, msg: String):
        """Handle status updates from WaypointNavigator."""
        status = msg.data
        self.get_logger().info(f"Navigator status: {status}")

        if self._active_mission is None:
            return

        if status == "ALL_COMPLETE":
            self._active_mission.status       = MissionStatus.COMPLETE
            self._active_mission.completed_at = time.time()
            elapsed = self._active_mission.completed_at - self._active_mission.created_at
            self.get_logger().info(
                f"Mission {self._active_mission.mission_id} COMPLETE in {elapsed:.1f}s"
            )
            self._publish_report()
            self._active_mission = None

        elif status.startswith("FAILED"):
            self._active_mission.status = MissionStatus.FAILED
            self.get_logger().error(f"Mission {self._active_mission.mission_id} FAILED: {status}")
            self._active_mission = None

        elif status.startswith("ARRIVED"):
            station = status.split(":")[-1]
            self.get_logger().info(f"  ✓ Robot arrived at {station}")

        elif status.startswith("DELIVERED"):
            station = status.split(":")[-1]
            self.get_logger().info(f"  📦 Package delivered at {station}")

    def _robot_status_cb(self, msg: String):
        self._robot_state = msg.data

    # ------------------------------------------------------------------
    # Queue processor
    # ------------------------------------------------------------------

    def _process_queue(self):
        """Dispatch the next queued mission when robot is idle."""
        if self._active_mission is not None:
            return   # already running a mission
        if not self._mission_queue:
            return   # nothing to do
        if self._robot_state != "IDLE":
            return   # robot busy

        mission = self._mission_queue.pop(0)
        mission.status = MissionStatus.IN_PROGRESS
        self._active_mission = mission

        self.get_logger().info(
            f"Dispatching mission {mission.mission_id}: {mission.destinations}"
        )

        order = String()
        order.data = ",".join(mission.destinations)
        self._order_pub.publish(order)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _publish_report(self):
        """Publish JSON status report."""
        report = {
            "active_mission": (
                self._active_mission.to_dict() if self._active_mission else None
            ),
            "queue_length": len(self._mission_queue),
            "robot_state":  self._robot_state,
            "queued": [m.to_dict() for m in self._mission_queue],
        }
        msg = String()
        msg.data = json.dumps(report, indent=2)
        self._report_pub.publish(msg)

    # ------------------------------------------------------------------
    # Convenience helpers (call programmatically or from CLI)
    # ------------------------------------------------------------------

    def add_mission(self, destinations: List[str], priority: int = 1, mission_id: str = None):
        """Add a delivery mission programmatically."""
        self._mission_counter += 1
        mid = mission_id or f"M{self._mission_counter:04d}"
        m = DeliveryMission(mission_id=mid, destinations=destinations, priority=priority)
        self._mission_queue.append(m)
        self.get_logger().info(f"Mission added programmatically: {mid}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(args=None):
    rclpy.init(args=args)
    node = DeliveryManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("DeliveryManager shutting down.")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
