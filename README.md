# 🤖 Autonomous Delivery Wheeled Robot — ROS2 Humble

A complete simulation of an autonomous wheeled delivery robot using:
- **Gazebo Classic** — physics simulation + warehouse world
- **SLAM Toolbox** — simultaneous localization and mapping
- **Nav2** — autonomous path planning and obstacle avoidance
- **RViz2** — visualization
- **Custom Python nodes** — waypoint sequencing and delivery management

---

## 📁 Package Structure

```
delivery_robot_ws/
└── src/
    └── delivery_robot/
        ├── CMakeLists.txt
        ├── package.xml
        ├── urdf/
        │   └── delivery_robot.urdf.xacro     # Robot model (diff-drive + LiDAR + camera)
        ├── worlds/
        │   └── delivery_world.world           # Warehouse with shelves & delivery stations
        ├── config/
        │   ├── nav2_params.yaml               # Nav2 stack configuration
        │   └── slam_toolbox_params.yaml       # SLAM Toolbox configuration
        ├── launch/
        │   ├── delivery_robot.launch.py       # ★ Master launch (slam or navigation mode)
        │   ├── gazebo.launch.py               # Gazebo + robot spawn
        │   ├── slam.launch.py                 # SLAM Toolbox
        │   ├── navigation.launch.py           # Nav2 stack
        │   └── rviz.launch.py                 # RViz2
        ├── delivery_robot/
        │   ├── __init__.py
        │   ├── waypoint_navigator.py          # Nav2 action client for waypoints
        │   └── delivery_manager.py            # High-level mission coordinator
        ├── maps/                              # Save your SLAM maps here
        └── rviz/
            └── delivery_robot.rviz            # RViz2 config
```

---

## ⚙️ Prerequisites

### System
- Ubuntu 22.04
- ROS2 Humble Hawksbill

### Install dependencies
```bash
sudo apt update && sudo apt install -y \
  ros-humble-gazebo-ros-pkgs \
  ros-humble-nav2-bringup \
  ros-humble-slam-toolbox \
  ros-humble-robot-state-publisher \
  ros-humble-joint-state-publisher \
  ros-humble-xacro \
  ros-humble-nav2-msgs \
  ros-humble-nav2-regulated-pure-pursuit-controller \
  ros-humble-tf2-tools \
  python3-colcon-common-extensions
```

---

## 🔨 Build

```bash
# 1. Navigate to workspace
cd ~/delivery_robot_ws

# 2. Source ROS2
source /opt/ros/humble/setup.bash

# 3. Build
colcon build --symlink-install

# 4. Source the workspace
source install/setup.bash
```

---

## 🗺️ WORKFLOW: Phase 1 — Build the Map (SLAM)

### Step 1: Launch in SLAM mode
```bash
ros2 launch delivery_robot delivery_robot.launch.py mode:=slam
```

This opens:
- Gazebo with the warehouse world and spawned robot
- SLAM Toolbox building a live map
- RViz2 showing the robot, LiDAR scan, and growing map

### Step 2: Teleoperate the robot to explore the environment
In a **new terminal**:
```bash
source /opt/ros/humble/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r /cmd_vel:=/cmd_vel
```
Drive around all areas of the warehouse until the map is complete.

### Step 3: Save the map
In a **new terminal**:
```bash
source /opt/ros/humble/setup.bash
ros2 run nav2_map_server map_saver_cli -f ~/delivery_robot_ws/src/delivery_robot/maps/delivery_map
```
This saves `delivery_map.pgm` and `delivery_map.yaml` into the `maps/` directory.

---

## 🚚 WORKFLOW: Phase 2 — Autonomous Delivery (Navigation)

### Step 1: Launch in navigation mode
```bash
ros2 launch delivery_robot delivery_robot.launch.py mode:=navigation
```

This starts:
- Gazebo simulation
- Nav2 with AMCL localization using your saved map
- WaypointNavigator and DeliveryManager nodes
- RViz2

### Step 2: Set initial pose in RViz2
1. In RViz2, click **"2D Pose Estimate"** tool
2. Click+drag on the map at the robot's approximate starting position
3. Wait for the green particle cloud (AMCL) to converge

### Step 3: Watch the demo delivery!
The `DeliveryManager` auto-queues a demo mission:
```
Home → Station A → Station B → Station C → Home
```

Monitor the delivery in a new terminal:
```bash
ros2 topic echo /delivery_status
ros2 topic echo /mission_report
```

### Step 4: Send a custom delivery order
```bash
ros2 service call /global_costmap/clear_entirely_global_costmap nav2_msgs/srv/ClearEntireCostmap {}

pes2ug23cs337@pes2ug23cs337:~/delivery_robot_ws$ ros2 service call /local_costmap/clear_entirely_local_costmap nav2_msgs/srv/ClearEntireCostmap {}

pes2ug23cs337@pes2ug23cs337:~/delivery_robot_ws$ ros2 topic pub --once /initialpose geometry_msgs/msg/PoseWithCovarianceStamped "{
  header: {frame_id: 'map'},
  pose: {pose: {position: {x: 0.0, y: 0.0, z: 0.0},
  orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}},
  covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.06853]}
}"

ros2 topic pub --once /robot_status std_msgs/String "{data: 'IDLE'}"

# Single station
ros2 topic pub --once /delivery_order std_msgs/String "{data: 'station_A'}" 

# Multi-stop route
ros2 topic pub --once /delivery_order std_msgs/String "data: 'station_A,station_B,station_C,home'"
```
---

## 🗺️ Delivery Stations

| Station     | X     | Y     | Description          |
|-------------|-------|-------|----------------------|
| `home`      | -7.0  | -7.0  | Charging / home base |
| `station_A` |  7.0  |  7.0  | Delivery point A (🟠) |
| `station_B` |  7.0  | -7.0  | Delivery point B (🟢) |
| `station_C` | -7.0  |  7.0  | Delivery point C (🔵) |
| `corridor_1`|  0.0  |  3.0  | Intermediate waypoint|
| `corridor_2`|  0.0  | -3.0  | Intermediate waypoint|

---

## 📊 Key ROS2 Topics

| Topic               | Type                     | Direction     | Description                        |
|---------------------|--------------------------|---------------|------------------------------------|
| `/cmd_vel`          | geometry_msgs/Twist      | Sub           | Velocity commands                  |
| `/odom`             | nav_msgs/Odometry        | Pub           | Wheel odometry                     |
| `/scan`             | sensor_msgs/LaserScan    | Pub           | LiDAR scan data                    |
| `/map`              | nav_msgs/OccupancyGrid   | Pub           | SLAM map                           |
| `/delivery_order`   | std_msgs/String          | Sub           | Comma-separated waypoint list      |
| `/delivery_status`  | std_msgs/String          | Pub           | Navigation progress updates        |
| `/robot_status`     | std_msgs/String          | Pub           | Current robot state                |
| `/new_mission`      | std_msgs/String          | Sub           | JSON mission for delivery manager  |
| `/mission_report`   | std_msgs/String          | Pub           | JSON mission status report         |

---

## 🐞 Troubleshooting

| Problem | Solution |
|---------|----------|
| Robot doesn't move | Confirm Nav2 is active: `ros2 node list \| grep nav2` |
| Map not loading | Check map path in `navigation.launch.py`; rebuild: `colcon build` |
| AMCL not localizing | Set 2D Pose Estimate in RViz2 near robot spawn point |
| LiDAR not showing | Check Gazebo plugin loaded: `ros2 topic echo /scan` |
| Nav2 goal rejected | Wait 10s for Nav2 to fully initialize, check costmaps in RViz2 |
| Build errors | Run `rosdep install --from-paths src --ignore-src -r -y` |

---

## 🔧 Customization

### Add a new delivery station
In `waypoint_navigator.py`, add to `DELIVERY_STATIONS`:
```python
"my_station": (x_coord, y_coord, yaw_degrees),
```

### Tune robot speed
In `config/nav2_params.yaml`, under `FollowPath`:
```yaml
desired_linear_vel: 0.4   # m/s (increase for faster delivery)
```

### Tune obstacle inflation
In `config/nav2_params.yaml`, under `inflation_layer`:
```yaml
inflation_radius: 0.55  # metres around obstacles
```
