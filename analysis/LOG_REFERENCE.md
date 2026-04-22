# Log field reference

Cached field catalog for the robot's WPILog + hoot logs. Scripts and agents can grep this file instead of probing a fresh log every time they need to know what signals are available.

_Generated: 2026-04-22 11:22:01 by `analysis/cache_log_keys.py`._

Sources scanned:
- WPILog: `logs/E1\FRC_20260418_151957_TXCMP1_E1.wpilog`  (831 fields)
- Hoot: `C:\Users\Jan\code\valor\vlogger\logs\E1\TXCMP1_E1\TXCMP1_E1_5431F5E34C324353202020590E1117FF_2026-04-18_15-19-53.hoot`  (1908 signals)
- Hoot: `C:\Users\Jan\code\valor\vlogger\logs\E1\TXCMP1_E1\TXCMP1_E1_rio_2026-04-18_15-19-53.hoot`  (443 signals)

Regenerate when the robot code adds/renames signals:
```bash
python -X utf8 analysis/cache_log_keys.py
```

---

## WPILog fields

### DS / FMS / System

_31 fields; 1 noise fields hidden (tune/mode/options/etc)._

| Name | Type |
|---|---|
| `DS:autonomous` | `boolean` |
| `DS:enabled` | `boolean` |
| `DS:estop` | `boolean` |
| `DS:joystick0/axes` | `float[]` |
| `DS:joystick0/buttons` | `boolean[]` |
| `DS:joystick0/povs` | `int64[]` |
| `DS:joystick1/axes` | `float[]` |
| `DS:joystick1/buttons` | `boolean[]` |
| `DS:joystick1/povs` | `int64[]` |
| `DS:joystick2/axes` | `float[]` |
| `DS:joystick2/buttons` | `boolean[]` |
| `DS:joystick2/povs` | `int64[]` |
| `DS:joystick3/axes` | `float[]` |
| `DS:joystick3/buttons` | `boolean[]` |
| `DS:joystick3/povs` | `int64[]` |
| `DS:joystick4/axes` | `float[]` |
| `DS:joystick4/buttons` | `boolean[]` |
| `DS:joystick4/povs` | `int64[]` |
| `DS:joystick5/axes` | `float[]` |
| `DS:joystick5/buttons` | `boolean[]` |
| `DS:joystick5/povs` | `int64[]` |
| `DS:test` | `boolean` |
| `NT:/FMSInfo/EventName` | `string` |
| `NT:/FMSInfo/FMSControlData` | `int64` |
| `NT:/FMSInfo/GameSpecificMessage` | `string` |
| `NT:/FMSInfo/IsRedAlliance` | `boolean` |
| `NT:/FMSInfo/MatchNumber` | `int64` |
| `NT:/FMSInfo/MatchType` | `int64` |
| `NT:/FMSInfo/ReplayNumber` | `int64` |
| `NT:/FMSInfo/StationNumber` | `int64` |
| `systemTime` | `int64` |

### Schema definitions

_10 fields._

| Name | Type |
|---|---|
| `NT:/.schema/struct:ChassisSpeeds` | `structschema` |
| `NT:/.schema/struct:Pose2d` | `structschema` |
| `NT:/.schema/struct:Pose3d` | `structschema` |
| `NT:/.schema/struct:Quaternion` | `structschema` |
| `NT:/.schema/struct:Rotation2d` | `structschema` |
| `NT:/.schema/struct:Rotation3d` | `structschema` |
| `NT:/.schema/struct:SwerveModulePosition` | `structschema` |
| `NT:/.schema/struct:SwerveModuleState` | `structschema` |
| `NT:/.schema/struct:Translation2d` | `structschema` |
| `NT:/.schema/struct:Translation3d` | `structschema` |

### Limelight (NT)

_192 fields._

| Name | Type |
|---|---|
| `NT:/CameraPublisher/limelight-center/description` | `string` |
| `NT:/CameraPublisher/limelight-center/mode` | `string` |
| `NT:/CameraPublisher/limelight-center/modes` | `string[]` |
| `NT:/CameraPublisher/limelight-center/source` | `string` |
| `NT:/CameraPublisher/limelight-center/streams` | `string[]` |
| `NT:/CameraPublisher/limelight-left/description` | `string` |
| `NT:/CameraPublisher/limelight-left/mode` | `string` |
| `NT:/CameraPublisher/limelight-left/modes` | `string[]` |
| `NT:/CameraPublisher/limelight-left/source` | `string` |
| `NT:/CameraPublisher/limelight-left/streams` | `string[]` |
| `NT:/CameraPublisher/limelight-right/description` | `string` |
| `NT:/CameraPublisher/limelight-right/mode` | `string` |
| `NT:/CameraPublisher/limelight-right/modes` | `string[]` |
| `NT:/CameraPublisher/limelight-right/source` | `string` |
| `NT:/CameraPublisher/limelight-right/streams` | `string[]` |
| `NT:/SmartDashboard/SwerveDrive/limelight-center/Active Camera` | `boolean` |
| `NT:/SmartDashboard/SwerveDrive/limelight-center/Doubts/Rotational` | `double` |
| `NT:/SmartDashboard/SwerveDrive/limelight-center/Doubts/Translational` | `double` |
| `NT:/SmartDashboard/SwerveDrive/limelight-center/Field Calibration/Distance to Tag` | `double` |
| `NT:/SmartDashboard/SwerveDrive/limelight-center/Vision Filter Pass` | `boolean` |
| `NT:/SmartDashboard/SwerveDrive/limelight-center/cameraPose` | `double[]` |
| `NT:/SmartDashboard/SwerveDrive/limelight-center/globalPos` | `struct:Pose2d` |
| `NT:/SmartDashboard/SwerveDrive/limelight-center/globalPosMegaTag2` | `struct:Pose2d` |
| `NT:/SmartDashboard/SwerveDrive/limelight-center/hasTarget` | `boolean` |
| `NT:/SmartDashboard/SwerveDrive/limelight-center/tid` | `int64` |
| `NT:/SmartDashboard/SwerveDrive/limelight-center/totalLatency` | `double` |
| `NT:/SmartDashboard/SwerveDrive/limelight-left/Active Camera` | `boolean` |
| `NT:/SmartDashboard/SwerveDrive/limelight-left/Doubts/Rotational` | `double` |
| `NT:/SmartDashboard/SwerveDrive/limelight-left/Doubts/Translational` | `double` |
| `NT:/SmartDashboard/SwerveDrive/limelight-left/Field Calibration/Distance to Tag` | `double` |
| `NT:/SmartDashboard/SwerveDrive/limelight-left/Vision Filter Pass` | `boolean` |
| `NT:/SmartDashboard/SwerveDrive/limelight-left/cameraPose` | `double[]` |
| `NT:/SmartDashboard/SwerveDrive/limelight-left/globalPos` | `struct:Pose2d` |
| `NT:/SmartDashboard/SwerveDrive/limelight-left/globalPosMegaTag2` | `struct:Pose2d` |
| `NT:/SmartDashboard/SwerveDrive/limelight-left/hasTarget` | `boolean` |
| `NT:/SmartDashboard/SwerveDrive/limelight-left/tid` | `int64` |
| `NT:/SmartDashboard/SwerveDrive/limelight-left/totalLatency` | `double` |
| `NT:/SmartDashboard/SwerveDrive/limelight-right/Active Camera` | `boolean` |
| `NT:/SmartDashboard/SwerveDrive/limelight-right/Doubts/Rotational` | `double` |
| `NT:/SmartDashboard/SwerveDrive/limelight-right/Doubts/Translational` | `double` |
| `NT:/SmartDashboard/SwerveDrive/limelight-right/Field Calibration/Distance to Tag` | `double` |
| `NT:/SmartDashboard/SwerveDrive/limelight-right/Vision Filter Pass` | `boolean` |
| `NT:/SmartDashboard/SwerveDrive/limelight-right/cameraPose` | `double[]` |
| `NT:/SmartDashboard/SwerveDrive/limelight-right/globalPos` | `struct:Pose2d` |
| `NT:/SmartDashboard/SwerveDrive/limelight-right/globalPosMegaTag2` | `struct:Pose2d` |
| `NT:/SmartDashboard/SwerveDrive/limelight-right/hasTarget` | `boolean` |
| `NT:/SmartDashboard/SwerveDrive/limelight-right/tid` | `int64` |
| `NT:/SmartDashboard/SwerveDrive/limelight-right/totalLatency` | `double` |
| `NT:/SmartDashboard/limelight-center_Interface` | `string` |
| `NT:/SmartDashboard/limelight-center_PipelineName` | `string` |
| `NT:/SmartDashboard/limelight-center_Stream` | `string` |
| `NT:/SmartDashboard/limelight-left_Interface` | `string` |
| `NT:/SmartDashboard/limelight-left_PipelineName` | `string` |
| `NT:/SmartDashboard/limelight-left_Stream` | `string` |
| `NT:/SmartDashboard/limelight-right_Interface` | `string` |
| `NT:/SmartDashboard/limelight-right_PipelineName` | `string` |
| `NT:/SmartDashboard/limelight-right_Stream` | `string` |
| `NT:/limelight-center/botpose` | `double[]` |
| `NT:/limelight-center/botpose_orb` | `double[]` |
| `NT:/limelight-center/botpose_orb_wpiblue` | `double[]` |
| `NT:/limelight-center/botpose_orb_wpired` | `double[]` |
| `NT:/limelight-center/botpose_targetspace` | `double[]` |
| `NT:/limelight-center/botpose_wpiblue` | `double[]` |
| `NT:/limelight-center/botpose_wpired` | `double[]` |
| `NT:/limelight-center/camerapose_robotspace` | `double[]` |
| `NT:/limelight-center/camerapose_robotspace_set` | `double[]` |
| `NT:/limelight-center/camerapose_targetspace` | `double[]` |
| `NT:/limelight-center/capture_rewind` | `double[]` |
| `NT:/limelight-center/cl` | `double` |
| `NT:/limelight-center/crosshairs` | `double[]` |
| `NT:/limelight-center/getpipe` | `double` |
| `NT:/limelight-center/getpipetype` | `string` |
| `NT:/limelight-center/hb` | `double` |
| `NT:/limelight-center/hw` | `double[]` |
| `NT:/limelight-center/imu` | `double[]` |
| `NT:/limelight-center/imuassistalpha_set` | `double` |
| `NT:/limelight-center/json` | `string` |
| `NT:/limelight-center/ledMode` | `double` |
| `NT:/limelight-center/llpython` | `double[]` |
| `NT:/limelight-center/pipeline` | `double` |
| `NT:/limelight-center/rawbarcodes` | `string[]` |
| `NT:/limelight-center/rawdetections` | `double[]` |
| `NT:/limelight-center/rawfiducials` | `double[]` |
| `NT:/limelight-center/rawtargets` | `double[]` |
| `NT:/limelight-center/snapshot` | `double` |
| `NT:/limelight-center/stddevs` | `double[]` |
| `NT:/limelight-center/stream` | `double` |
| `NT:/limelight-center/t2d` | `double[]` |
| `NT:/limelight-center/ta` | `double` |
| `NT:/limelight-center/targetpose_cameraspace` | `double[]` |
| `NT:/limelight-center/targetpose_robotspace` | `double[]` |
| `NT:/limelight-center/tc` | `double[]` |
| `NT:/limelight-center/tcclass` | `string` |
| `NT:/limelight-center/tdclass` | `string` |
| `NT:/limelight-center/throttle_set` | `double` |
| `NT:/limelight-center/tid` | `double` |
| `NT:/limelight-center/tl` | `double` |
| `NT:/limelight-center/tv` | `double` |
| `NT:/limelight-center/tx` | `double` |
| `NT:/limelight-center/txnc` | `double` |
| `NT:/limelight-center/ty` | `double` |
| `NT:/limelight-center/tync` | `double` |
| `NT:/limelight-left/botpose` | `double[]` |
| `NT:/limelight-left/botpose_orb` | `double[]` |
| `NT:/limelight-left/botpose_orb_wpiblue` | `double[]` |
| `NT:/limelight-left/botpose_orb_wpired` | `double[]` |
| `NT:/limelight-left/botpose_targetspace` | `double[]` |
| `NT:/limelight-left/botpose_wpiblue` | `double[]` |
| `NT:/limelight-left/botpose_wpired` | `double[]` |
| `NT:/limelight-left/camerapose_robotspace` | `double[]` |
| `NT:/limelight-left/camerapose_robotspace_set` | `double[]` |
| `NT:/limelight-left/camerapose_targetspace` | `double[]` |
| `NT:/limelight-left/capture_rewind` | `double[]` |
| `NT:/limelight-left/cl` | `double` |
| `NT:/limelight-left/crosshairs` | `double[]` |
| `NT:/limelight-left/getpipe` | `double` |
| `NT:/limelight-left/getpipetype` | `string` |
| `NT:/limelight-left/hb` | `double` |
| `NT:/limelight-left/hw` | `double[]` |
| `NT:/limelight-left/imu` | `double[]` |
| `NT:/limelight-left/imuassistalpha_set` | `double` |
| `NT:/limelight-left/json` | `string` |
| `NT:/limelight-left/ledMode` | `double` |
| `NT:/limelight-left/llpython` | `double[]` |
| `NT:/limelight-left/pipeline` | `double` |
| `NT:/limelight-left/rawbarcodes` | `string[]` |
| `NT:/limelight-left/rawdetections` | `double[]` |
| `NT:/limelight-left/rawfiducials` | `double[]` |
| `NT:/limelight-left/rawtargets` | `double[]` |
| `NT:/limelight-left/snapshot` | `double` |
| `NT:/limelight-left/stddevs` | `double[]` |
| `NT:/limelight-left/stream` | `double` |
| `NT:/limelight-left/t2d` | `double[]` |
| `NT:/limelight-left/ta` | `double` |
| `NT:/limelight-left/targetpose_cameraspace` | `double[]` |
| `NT:/limelight-left/targetpose_robotspace` | `double[]` |
| `NT:/limelight-left/tc` | `double[]` |
| `NT:/limelight-left/tcclass` | `string` |
| `NT:/limelight-left/tdclass` | `string` |
| `NT:/limelight-left/throttle_set` | `double` |
| `NT:/limelight-left/tid` | `double` |
| `NT:/limelight-left/tl` | `double` |
| `NT:/limelight-left/tv` | `double` |
| `NT:/limelight-left/tx` | `double` |
| `NT:/limelight-left/txnc` | `double` |
| `NT:/limelight-left/ty` | `double` |
| `NT:/limelight-left/tync` | `double` |
| `NT:/limelight-right/botpose` | `double[]` |
| `NT:/limelight-right/botpose_orb` | `double[]` |
| `NT:/limelight-right/botpose_orb_wpiblue` | `double[]` |
| `NT:/limelight-right/botpose_orb_wpired` | `double[]` |
| `NT:/limelight-right/botpose_targetspace` | `double[]` |
| `NT:/limelight-right/botpose_wpiblue` | `double[]` |
| `NT:/limelight-right/botpose_wpired` | `double[]` |
| `NT:/limelight-right/camerapose_robotspace` | `double[]` |
| `NT:/limelight-right/camerapose_robotspace_set` | `double[]` |
| `NT:/limelight-right/camerapose_targetspace` | `double[]` |
| `NT:/limelight-right/capture_rewind` | `double[]` |
| `NT:/limelight-right/cl` | `double` |
| `NT:/limelight-right/crosshairs` | `double[]` |
| `NT:/limelight-right/getpipe` | `double` |
| `NT:/limelight-right/getpipetype` | `string` |
| `NT:/limelight-right/hb` | `double` |
| `NT:/limelight-right/hw` | `double[]` |
| `NT:/limelight-right/imu` | `double[]` |
| `NT:/limelight-right/imuassistalpha_set` | `double` |
| `NT:/limelight-right/json` | `string` |
| `NT:/limelight-right/ledMode` | `double` |
| `NT:/limelight-right/llpython` | `double[]` |
| `NT:/limelight-right/pipeline` | `double` |
| `NT:/limelight-right/rawbarcodes` | `string[]` |
| `NT:/limelight-right/rawdetections` | `double[]` |
| `NT:/limelight-right/rawfiducials` | `double[]` |
| `NT:/limelight-right/rawtargets` | `double[]` |
| `NT:/limelight-right/snapshot` | `double` |
| `NT:/limelight-right/stddevs` | `double[]` |
| `NT:/limelight-right/stream` | `double` |
| `NT:/limelight-right/t2d` | `double[]` |
| `NT:/limelight-right/ta` | `double` |
| `NT:/limelight-right/targetpose_cameraspace` | `double[]` |
| `NT:/limelight-right/targetpose_robotspace` | `double[]` |
| `NT:/limelight-right/tc` | `double[]` |
| `NT:/limelight-right/tcclass` | `string` |
| `NT:/limelight-right/tdclass` | `string` |
| `NT:/limelight-right/throttle_set` | `double` |
| `NT:/limelight-right/tid` | `double` |
| `NT:/limelight-right/tl` | `double` |
| `NT:/limelight-right/tv` | `double` |
| `NT:/limelight-right/tx` | `double` |
| `NT:/limelight-right/txnc` | `double` |
| `NT:/limelight-right/ty` | `double` |
| `NT:/limelight-right/tync` | `double` |

### Shooter / Flywheel / Hood

_34 fields; 72 noise fields hidden (tune/mode/options/etc)._

| Name | Type |
|---|---|
| `NT:/SmartDashboard/Shooter/Current Target Pose` | `struct:Pose2d` |
| `NT:/SmartDashboard/Shooter/Delta Time` | `double` |
| `NT:/SmartDashboard/Shooter/Field Calibration/Shooter distance to Target` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Left Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Left Motor/Position` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Left Motor/Speed` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Left Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Left Motor/reqSpeed` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Right One Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Right One Motor/Position` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Right One Motor/Speed` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Right One Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Right One Motor/reqSpeed` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Right Two Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Right Two Motor/Position` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Right Two Motor/Speed` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Right Two Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel Right Two Motor/reqSpeed` | `double` |
| `NT:/SmartDashboard/Shooter/Flywheel State` | `string` |
| `NT:/SmartDashboard/Shooter/Hood Motor/Absolute Position` | `double` |
| `NT:/SmartDashboard/Shooter/Hood Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/Shooter/Hood Motor/Position` | `double` |
| `NT:/SmartDashboard/Shooter/Hood Motor/Speed` | `double` |
| `NT:/SmartDashboard/Shooter/Hood Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/Shooter/Hood Motor/reqPosition` | `double` |
| `NT:/SmartDashboard/Shooter/Hood Robot Relative` | `struct:Pose3d` |
| `NT:/SmartDashboard/Shooter/Hood State` | `string` |
| `NT:/SmartDashboard/Shooter/Hood World Relative` | `struct:Pose3d` |
| `NT:/SmartDashboard/Shooter/Is System Ready` | `string` |
| `NT:/SmartDashboard/Shooter/Pit Mode` | `boolean` |
| `NT:/SmartDashboard/Shooter/Predicted Pose` | `struct:Pose2d` |
| `NT:/SmartDashboard/Shooter/Projectile Aiming Mode` | `string` |
| `NT:/SmartDashboard/Shooter/Turret Robot Relative` | `struct:Pose3d` |
| `NT:/SmartDashboard/Shooter/Turret World Relative` | `struct:Pose3d` |

### Intake / Hopper / Feeder

_54 fields; 126 noise fields hidden (tune/mode/options/etc)._

| Name | Type |
|---|---|
| `NT:/SmartDashboard/Intake/Activate Shooting Stance` | `boolean` |
| `NT:/SmartDashboard/Intake/All Outtake` | `boolean` |
| `NT:/SmartDashboard/Intake/BEFORE MOTOR SET Hopper State` | `string` |
| `NT:/SmartDashboard/Intake/Can I Shoot` | `string` |
| `NT:/SmartDashboard/Intake/Can I Shoot Boolean` | `boolean` |
| `NT:/SmartDashboard/Intake/Can I Shuttle` | `string` |
| `NT:/SmartDashboard/Intake/Can I Shuttle Boolean` | `boolean` |
| `NT:/SmartDashboard/Intake/Dumper State` | `string` |
| `NT:/SmartDashboard/Intake/Enable Rotation Align` | `boolean` |
| `NT:/SmartDashboard/Intake/Feeder State` | `string` |
| `NT:/SmartDashboard/Intake/Hopper State` | `string` |
| `NT:/SmartDashboard/Intake/Intake Jam` | `boolean` |
| `NT:/SmartDashboard/Intake/Intake Robot Relative` | `struct:Pose3d` |
| `NT:/SmartDashboard/Intake/Intake State` | `string` |
| `NT:/SmartDashboard/Intake/Left Feeder Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/Intake/Left Feeder Motor/Position` | `double` |
| `NT:/SmartDashboard/Intake/Left Feeder Motor/Speed` | `double` |
| `NT:/SmartDashboard/Intake/Left Feeder Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/Intake/Left Feeder Motor/reqSpeed` | `double` |
| `NT:/SmartDashboard/Intake/Left Hopper Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/Intake/Left Hopper Motor/Position` | `double` |
| `NT:/SmartDashboard/Intake/Left Hopper Motor/Speed` | `double` |
| `NT:/SmartDashboard/Intake/Left Hopper Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/Intake/Left Hopper Motor/reqSpeed` | `double` |
| `NT:/SmartDashboard/Intake/Left Intake Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/Intake/Left Intake Motor/Position` | `double` |
| `NT:/SmartDashboard/Intake/Left Intake Motor/Speed` | `double` |
| `NT:/SmartDashboard/Intake/Left Intake Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/Intake/Left Intake Motor/Supply Current` | `double` |
| `NT:/SmartDashboard/Intake/Left Intake Motor/reqSpeed` | `double` |
| `NT:/SmartDashboard/Intake/Pivot Control Mode` | `string` |
| `NT:/SmartDashboard/Intake/Pivot Flop Deployment` | `boolean` |
| `NT:/SmartDashboard/Intake/Pivot Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/Intake/Pivot Motor/Position` | `double` |
| `NT:/SmartDashboard/Intake/Pivot Motor/Speed` | `double` |
| `NT:/SmartDashboard/Intake/Pivot Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/Intake/Pivot Motor/reqPosition` | `double` |
| `NT:/SmartDashboard/Intake/Pivot State` | `string` |
| `NT:/SmartDashboard/Intake/Right Feeder Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/Intake/Right Feeder Motor/Position` | `double` |
| `NT:/SmartDashboard/Intake/Right Feeder Motor/Speed` | `double` |
| `NT:/SmartDashboard/Intake/Right Feeder Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/Intake/Right Feeder Motor/reqSpeed` | `double` |
| `NT:/SmartDashboard/Intake/Right Hopper Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/Intake/Right Hopper Motor/Position` | `double` |
| `NT:/SmartDashboard/Intake/Right Hopper Motor/Speed` | `double` |
| `NT:/SmartDashboard/Intake/Right Hopper Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/Intake/Right Hopper Motor/reqSpeed` | `double` |
| `NT:/SmartDashboard/Intake/Right Intake Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/Intake/Right Intake Motor/Position` | `double` |
| `NT:/SmartDashboard/Intake/Right Intake Motor/Speed` | `double` |
| `NT:/SmartDashboard/Intake/Right Intake Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/Intake/Right Intake Motor/Supply Current` | `double` |
| `NT:/SmartDashboard/Intake/Right Intake Motor/reqSpeed` | `double` |

### Swerve Drive modules

_56 fields; 128 noise fields hidden (tune/mode/options/etc)._

| Name | Type |
|---|---|
| `NT:/SmartDashboard/SwerveDrive/Module 0/Azimuth Motor/Absolute Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/Azimuth Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/Azimuth Motor/Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/Azimuth Motor/Speed` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/Azimuth Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/Azimuth Motor/reqPosition` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/Desired State` | `struct:SwerveModuleState` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/Drive Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/Drive Motor/Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/Drive Motor/Speed` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/Drive Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/Drive Motor/reqSpeed` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/Position` | `struct:SwerveModulePosition` |
| `NT:/SmartDashboard/SwerveDrive/Module 0/State` | `struct:SwerveModuleState` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Azimuth Motor/Absolute Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Azimuth Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Azimuth Motor/Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Azimuth Motor/Speed` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Azimuth Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Azimuth Motor/reqPosition` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Desired State` | `struct:SwerveModuleState` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Drive Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Drive Motor/Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Drive Motor/Speed` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Drive Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Drive Motor/reqSpeed` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/Position` | `struct:SwerveModulePosition` |
| `NT:/SmartDashboard/SwerveDrive/Module 1/State` | `struct:SwerveModuleState` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Azimuth Motor/Absolute Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Azimuth Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Azimuth Motor/Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Azimuth Motor/Speed` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Azimuth Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Azimuth Motor/reqPosition` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Desired State` | `struct:SwerveModuleState` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Drive Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Drive Motor/Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Drive Motor/Speed` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Drive Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Drive Motor/reqSpeed` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/Position` | `struct:SwerveModulePosition` |
| `NT:/SmartDashboard/SwerveDrive/Module 2/State` | `struct:SwerveModuleState` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Azimuth Motor/Absolute Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Azimuth Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Azimuth Motor/Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Azimuth Motor/Speed` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Azimuth Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Azimuth Motor/reqPosition` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Desired State` | `struct:SwerveModuleState` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Drive Motor/Out Volt` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Drive Motor/Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Drive Motor/Speed` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Drive Motor/Stator Current` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Drive Motor/reqSpeed` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/Position` | `struct:SwerveModulePosition` |
| `NT:/SmartDashboard/SwerveDrive/Module 3/State` | `struct:SwerveModuleState` |

### Swerve Drive (other)

_59 fields._

| Name | Type |
|---|---|
| `NT:/SmartDashboard/SwerveDrive/Acceleration` | `double[]` |
| `NT:/SmartDashboard/SwerveDrive/Actual Calculated Pose` | `struct:Pose2d` |
| `NT:/SmartDashboard/SwerveDrive/Actual Raw Pose` | `struct:Pose2d` |
| `NT:/SmartDashboard/SwerveDrive/Angular Velocity` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Commanded Speeds` | `struct:ChassisSpeeds` |
| `NT:/SmartDashboard/SwerveDrive/Delta Time` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Driver Rotation State` | `string` |
| `NT:/SmartDashboard/SwerveDrive/Driver Translation State` | `string` |
| `NT:/SmartDashboard/SwerveDrive/Enable Rotation Align` | `boolean` |
| `NT:/SmartDashboard/SwerveDrive/Field Calibration/Angle Offset` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Field Calibration/Toast` | `boolean` |
| `NT:/SmartDashboard/SwerveDrive/Gyro Pitch` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Gyro Roll` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Gyro Yaw` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/Goal Pose` | `struct:Pose2d` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/RotController/Current Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/RotController/Current Position Error` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/RotController/Current Velocity` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/RotController/Current Velocity Error` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/RotController/Goal Error` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/RotController/Goal Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/RotController/Goal Velocity` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/RotController/Setpoint Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/RotController/Setpoint Velocity` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/RotController/Velocity Error` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/Setpoint Pose` | `struct:Pose2d` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/XController/Current Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/XController/Current Position Error` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/XController/Current Velocity` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/XController/Current Velocity Error` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/XController/Goal Error` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/XController/Goal Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/XController/Goal Velocity` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/XController/Setpoint Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/XController/Setpoint Velocity` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/XController/Velocity Error` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/YController/Current Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/YController/Current Position Error` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/YController/Current Velocity` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/YController/Current Velocity Error` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/YController/Goal Error` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/YController/Goal Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/YController/Goal Velocity` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/YController/Setpoint Position` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/YController/Setpoint Velocity` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Intake Align/YController/Velocity Error` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Max Rotational Velocity` | `double` |
| `NT:/SmartDashboard/SwerveDrive/ROT_D` | `double` |
| `NT:/SmartDashboard/SwerveDrive/ROT_I` | `double` |
| `NT:/SmartDashboard/SwerveDrive/ROT_KFF` | `double` |
| `NT:/SmartDashboard/SwerveDrive/ROT_P` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Robot Velocities` | `struct:ChassisSpeeds` |
| `NT:/SmartDashboard/SwerveDrive/Rotation Target` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Swerve States` | `struct:SwerveModuleState[]` |
| `NT:/SmartDashboard/SwerveDrive/Trajectory Follower/Commanded Auto Speeds` | `struct:ChassisSpeeds` |
| `NT:/SmartDashboard/SwerveDrive/Trajectory Follower/Current Pose` | `struct:Pose2d` |
| `NT:/SmartDashboard/SwerveDrive/Trajectory Follower/End Time` | `double` |
| `NT:/SmartDashboard/SwerveDrive/Trajectory Follower/Goal Pose` | `struct:Pose2d` |
| `NT:/SmartDashboard/SwerveDrive/Trajectory Follower/Time Elapsed` | `double` |

### Power Distribution

_27 fields; 3 noise fields hidden (tune/mode/options/etc)._

| Name | Type |
|---|---|
| `NT:/SmartDashboard/Power Distribution/Chan0` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan1` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan10` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan11` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan12` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan13` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan14` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan15` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan16` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan17` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan18` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan19` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan2` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan20` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan21` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan22` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan23` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan3` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan4` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan5` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan6` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan7` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan8` | `double` |
| `NT:/SmartDashboard/Power Distribution/Chan9` | `double` |
| `NT:/SmartDashboard/Power Distribution/SwitchableChannel` | `boolean` |
| `NT:/SmartDashboard/Power Distribution/TotalCurrent` | `double` |
| `NT:/SmartDashboard/Power Distribution/Voltage` | `double` |

### Auto / Trajectory

_0 fields; 8 noise fields hidden (tune/mode/options/etc)._

| Name | Type |
|---|---|

### Smart Dashboard (misc)

_11 fields; 10 noise fields hidden (tune/mode/options/etc)._

| Name | Type |
|---|---|
| `NT:/SmartDashboard/Alerts/errors` | `string[]` |
| `NT:/SmartDashboard/Alerts/infos` | `string[]` |
| `NT:/SmartDashboard/Alerts/warnings` | `string[]` |
| `NT:/SmartDashboard/Battery Voltage` | `double` |
| `NT:/SmartDashboard/Match Data/ActiveAlliance` | `string` |
| `NT:/SmartDashboard/Match Data/CanScore` | `boolean` |
| `NT:/SmartDashboard/Match Data/CurrentShift` | `double` |
| `NT:/SmartDashboard/Match Data/GameData` | `string` |
| `NT:/SmartDashboard/Match Data/MatchTime` | `double` |
| `NT:/SmartDashboard/Match Data/TimeLeftInPeriod` | `double` |
| `NT:/SmartDashboard/Serial Number` | `string` |

### Other NT

_5 fields; 1 noise fields hidden (tune/mode/options/etc)._

| Name | Type |
|---|---|
| `NT:/LiveWindow/.status/LW Enabled` | `boolean` |
| `NT:/PathPlanner/currentPose` | `struct:Pose2d` |
| `NT:/PathPlanner/targetPose` | `struct:Pose2d` |
| `NT:/PathPlanner/vel` | `double[]` |
| `NT:/Shuffleboard/.metadata/Selected` | `string` |

### Other / Uncategorized

_3 fields._

| Name | Type |
|---|---|
| `NTConnection` | `json` |
| `console` | `string` |
| `messages` | `string` |

---

## Hoot (Phoenix) signals

Hoot logs require `owlet` to decode. Signal IDs below are the hex values owlet uses with `-s` for filtered extraction (passing only the IDs you want keeps decode time to a second or two).

### `TXCMP1_E1_5431F5E34C324353202020590E1117FF_2026-04-18_15-19-53.hoot`

_1908 signals._

#### `CANcoder-20`

| Signal | Hex ID |
|---|---|
| `AbsolutePosition` | `7a21401` |
| `FaultField` | `34c1401` |
| `Fault_BadMagnet` | `273e1401` |
| `Fault_BootDuringEnable` | `271d1401` |
| `Fault_Hardware` | `27111401` |
| `Fault_Undervoltage` | `271a1401` |
| `Fault_UnlicensedFeatureInUse` | `27201401` |
| `IsProLicensed` | `8041401` |
| `MagnetHealth` | `7a71401` |
| `Position` | `7a11401` |
| `PositionSinceBoot` | `7a51401` |
| `StickyFaultField` | `34d1401` |
| `StickyFault_BadMagnet` | `273f1401` |
| `StickyFault_BootDuringEnable` | `271e1401` |
| `StickyFault_Hardware` | `27121401` |
| `StickyFault_Undervoltage` | `271b1401` |
| `StickyFault_UnlicensedFeatureInUse` | `27211401` |
| `SupplyVoltage` | `7a61401` |
| `UnfilteredVelocity` | `7a41401` |
| `Velocity` | `7a01401` |
| `Version` | `2e21401` |
| `VersionBugfix` | `2e01401` |
| `VersionBuild` | `2e11401` |
| `VersionMajor` | `2de1401` |
| `VersionMinor` | `2df1401` |

#### `CANcoder-21`

| Signal | Hex ID |
|---|---|
| `AbsolutePosition` | `7a21501` |
| `FaultField` | `34c1501` |
| `Fault_BadMagnet` | `273e1501` |
| `Fault_BootDuringEnable` | `271d1501` |
| `Fault_Hardware` | `27111501` |
| `Fault_Undervoltage` | `271a1501` |
| `Fault_UnlicensedFeatureInUse` | `27201501` |
| `IsProLicensed` | `8041501` |
| `MagnetHealth` | `7a71501` |
| `Position` | `7a11501` |
| `PositionSinceBoot` | `7a51501` |
| `StickyFaultField` | `34d1501` |
| `StickyFault_BadMagnet` | `273f1501` |
| `StickyFault_BootDuringEnable` | `271e1501` |
| `StickyFault_Hardware` | `27121501` |
| `StickyFault_Undervoltage` | `271b1501` |
| `StickyFault_UnlicensedFeatureInUse` | `27211501` |
| `SupplyVoltage` | `7a61501` |
| `UnfilteredVelocity` | `7a41501` |
| `Velocity` | `7a01501` |
| `Version` | `2e21501` |
| `VersionBugfix` | `2e01501` |
| `VersionBuild` | `2e11501` |
| `VersionMajor` | `2de1501` |
| `VersionMinor` | `2df1501` |

#### `CANcoder-22`

| Signal | Hex ID |
|---|---|
| `AbsolutePosition` | `7a21601` |
| `FaultField` | `34c1601` |
| `Fault_BadMagnet` | `273e1601` |
| `Fault_BootDuringEnable` | `271d1601` |
| `Fault_Hardware` | `27111601` |
| `Fault_Undervoltage` | `271a1601` |
| `Fault_UnlicensedFeatureInUse` | `27201601` |
| `IsProLicensed` | `8041601` |
| `MagnetHealth` | `7a71601` |
| `Position` | `7a11601` |
| `PositionSinceBoot` | `7a51601` |
| `StickyFaultField` | `34d1601` |
| `StickyFault_BadMagnet` | `273f1601` |
| `StickyFault_BootDuringEnable` | `271e1601` |
| `StickyFault_Hardware` | `27121601` |
| `StickyFault_Undervoltage` | `271b1601` |
| `StickyFault_UnlicensedFeatureInUse` | `27211601` |
| `SupplyVoltage` | `7a61601` |
| `UnfilteredVelocity` | `7a41601` |
| `Velocity` | `7a01601` |
| `Version` | `2e21601` |
| `VersionBugfix` | `2e01601` |
| `VersionBuild` | `2e11601` |
| `VersionMajor` | `2de1601` |
| `VersionMinor` | `2df1601` |

#### `CANcoder-23`

| Signal | Hex ID |
|---|---|
| `AbsolutePosition` | `7a21701` |
| `FaultField` | `34c1701` |
| `Fault_BadMagnet` | `273e1701` |
| `Fault_BootDuringEnable` | `271d1701` |
| `Fault_Hardware` | `27111701` |
| `Fault_Undervoltage` | `271a1701` |
| `Fault_UnlicensedFeatureInUse` | `27201701` |
| `IsProLicensed` | `8041701` |
| `MagnetHealth` | `7a71701` |
| `Position` | `7a11701` |
| `PositionSinceBoot` | `7a51701` |
| `StickyFaultField` | `34d1701` |
| `StickyFault_BadMagnet` | `273f1701` |
| `StickyFault_BootDuringEnable` | `271e1701` |
| `StickyFault_Hardware` | `27121701` |
| `StickyFault_Undervoltage` | `271b1701` |
| `StickyFault_UnlicensedFeatureInUse` | `27211701` |
| `SupplyVoltage` | `7a61701` |
| `UnfilteredVelocity` | `7a41701` |
| `Velocity` | `7a01701` |
| `Version` | `2e21701` |
| `VersionBugfix` | `2e01701` |
| `VersionBuild` | `2e11701` |
| `VersionMajor` | `2de1701` |
| `VersionMinor` | `2df1701` |

#### `CANcoder-26`

| Signal | Hex ID |
|---|---|
| `AbsolutePosition` | `7a21a01` |
| `FaultField` | `34c1a01` |
| `Fault_BadMagnet` | `273e1a01` |
| `Fault_BootDuringEnable` | `271d1a01` |
| `Fault_Hardware` | `27111a01` |
| `Fault_Undervoltage` | `271a1a01` |
| `Fault_UnlicensedFeatureInUse` | `27201a01` |
| `IsProLicensed` | `8041a01` |
| `MagnetHealth` | `7a71a01` |
| `Position` | `7a11a01` |
| `PositionSinceBoot` | `7a51a01` |
| `StickyFaultField` | `34d1a01` |
| `StickyFault_BadMagnet` | `273f1a01` |
| `StickyFault_BootDuringEnable` | `271e1a01` |
| `StickyFault_Hardware` | `27121a01` |
| `StickyFault_Undervoltage` | `271b1a01` |
| `StickyFault_UnlicensedFeatureInUse` | `27211a01` |
| `SupplyVoltage` | `7a61a01` |
| `UnfilteredVelocity` | `7a41a01` |
| `Velocity` | `7a01a01` |
| `Version` | `2e21a01` |
| `VersionBugfix` | `2e01a01` |
| `VersionBuild` | `2e11a01` |
| `VersionMajor` | `2de1a01` |
| `VersionMinor` | `2df1a01` |

#### `CANdle-60`

| Signal | Hex ID |
|---|---|
| `DeviceTemp` | `a5a3c06` |
| `FaultField` | `34c3c06` |
| `Fault_5VTooHigh` | `27923c06` |
| `Fault_5VTooLow` | `27953c06` |
| `Fault_BootDuringEnable` | `271d3c06` |
| `Fault_Hardware` | `27113c06` |
| `Fault_Overvoltage` | `278f3c06` |
| `Fault_ShortCircuit` | `279e3c06` |
| `Fault_SoftwareFuse` | `279b3c06` |
| `Fault_Thermal` | `27983c06` |
| `Fault_Undervoltage` | `271a3c06` |
| `Fault_UnlicensedFeatureInUse` | `27203c06` |
| `FiveVRailVoltage` | `a583c06` |
| `IsProLicensed` | `8043c06` |
| `MaxSimultaneousAnimationCount` | `a5c3c06` |
| `OutputCurrent` | `a593c06` |
| `StickyFaultField` | `34d3c06` |
| `StickyFault_5VTooHigh` | `27933c06` |
| `StickyFault_5VTooLow` | `27963c06` |
| `StickyFault_BootDuringEnable` | `271e3c06` |
| `StickyFault_Hardware` | `27123c06` |
| `StickyFault_Overvoltage` | `27903c06` |
| `StickyFault_ShortCircuit` | `279f3c06` |
| `StickyFault_SoftwareFuse` | `279c3c06` |
| `StickyFault_Thermal` | `27993c06` |
| `StickyFault_Undervoltage` | `271b3c06` |
| `StickyFault_UnlicensedFeatureInUse` | `27213c06` |
| `SupplyVoltage` | `a573c06` |
| `VBatModulation` | `a5b3c06` |
| `Version` | `2e23c06` |
| `VersionBugfix` | `2e03c06` |
| `VersionBuild` | `2e13c06` |
| `VersionMajor` | `2de3c06` |
| `VersionMinor` | `2df3c06` |

#### `CANrange-40`

| Signal | Hex ID |
|---|---|
| `AmbientSignal` | `8622804` |
| `Distance` | `85c2804` |
| `DistanceStdDev` | `8632804` |
| `FaultField` | `34c2804` |
| `Fault_BootDuringEnable` | `271d2804` |
| `Fault_Hardware` | `27112804` |
| `Fault_Undervoltage` | `271a2804` |
| `Fault_UnlicensedFeatureInUse` | `27202804` |
| `IsDetected` | `8602804` |
| `IsProLicensed` | `8042804` |
| `MeasurementHealth` | `8612804` |
| `MeasurementTime` | `85e2804` |
| `RealFOVCenterX` | `8662804` |
| `RealFOVCenterY` | `8672804` |
| `RealFOVRangeX` | `8682804` |
| `RealFOVRangeY` | `8692804` |
| `SignalStrength` | `85f2804` |
| `StickyFaultField` | `34d2804` |
| `StickyFault_BootDuringEnable` | `271e2804` |
| `StickyFault_Hardware` | `27122804` |
| `StickyFault_Undervoltage` | `271b2804` |
| `StickyFault_UnlicensedFeatureInUse` | `27212804` |
| `SupplyVoltage` | `85b2804` |
| `Version` | `2e22804` |
| `VersionBugfix` | `2e02804` |
| `VersionBuild` | `2e12804` |
| `VersionMajor` | `2de2804` |
| `VersionMinor` | `2df2804` |

#### `Other`

| Signal | Hex ID |
|---|---|
| `AllianceStation` | `5ff00` |
| `RobotEnable` | `1ff00` |
| `RobotMode` | `4ff00` |

#### `Pigeon2-61`

| Signal | Hex ID |
|---|---|
| `AccelerationX` | `3ca3d02` |
| `AccelerationY` | `3cb3d02` |
| `AccelerationZ` | `3cc3d02` |
| `AccumGyroX` | `3c43d02` |
| `AccumGyroY` | `3c53d02` |
| `AccumGyroZ` | `3c63d02` |
| `AngularVelocityXDevice` | `3d03d02` |
| `AngularVelocityXWorld` | `3c73d02` |
| `AngularVelocityYDevice` | `3d13d02` |
| `AngularVelocityYWorld` | `3c83d02` |
| `AngularVelocityZDevice` | `3d23d02` |
| `AngularVelocityZWorld` | `3c93d02` |
| `FaultField` | `34c3d02` |
| `Fault_BootDuringEnable` | `271d3d02` |
| `Fault_BootIntoMotion` | `272c3d02` |
| `Fault_BootupAccelerometer` | `27233d02` |
| `Fault_BootupGyroscope` | `27263d02` |
| `Fault_BootupMagnetometer` | `27293d02` |
| `Fault_DataAcquiredLate` | `272f3d02` |
| `Fault_Hardware` | `27113d02` |
| `Fault_LoopTimeSlow` | `27323d02` |
| `Fault_SaturatedAccelerometer` | `27383d02` |
| `Fault_SaturatedGyroscope` | `273b3d02` |
| `Fault_SaturatedMagnetometer` | `27353d02` |
| `Fault_Undervoltage` | `271a3d02` |
| `Fault_UnlicensedFeatureInUse` | `27203d02` |
| `GravityVectorX` | `3bc3d02` |
| `GravityVectorY` | `3bd3d02` |
| `GravityVectorZ` | `3be3d02` |
| `IsProLicensed` | `8043d02` |
| `MagneticFieldX` | `3d53d02` |
| `MagneticFieldY` | `3d63d02` |
| `MagneticFieldZ` | `3d73d02` |
| `NoMotionCount` | `3c13d02` |
| `NoMotionEnabled` | `3c03d02` |
| `Pitch` | `3b63d02` |
| `QuatW` | `3b83d02` |
| `QuatX` | `3b93d02` |
| `QuatY` | `3ba3d02` |
| `QuatZ` | `3bb3d02` |
| `RawMagneticFieldX` | `3d83d02` |
| `RawMagneticFieldY` | `3d93d02` |
| `RawMagneticFieldZ` | `3da3d02` |
| `Roll` | `3b73d02` |
| `StickyFaultField` | `34d3d02` |
| `StickyFault_BootDuringEnable` | `271e3d02` |
| `StickyFault_BootIntoMotion` | `272d3d02` |
| `StickyFault_BootupAccelerometer` | `27243d02` |
| `StickyFault_BootupGyroscope` | `27273d02` |
| `StickyFault_BootupMagnetometer` | `272a3d02` |
| `StickyFault_DataAcquiredLate` | `27303d02` |
| `StickyFault_Hardware` | `27123d02` |
| `StickyFault_LoopTimeSlow` | `27333d02` |
| `StickyFault_SaturatedAccelerometer` | `27393d02` |
| `StickyFault_SaturatedGyroscope` | `273c3d02` |
| `StickyFault_SaturatedMagnetometer` | `27363d02` |
| `StickyFault_Undervoltage` | `271b3d02` |
| `StickyFault_UnlicensedFeatureInUse` | `27213d02` |
| `SupplyVoltage` | `3cd3d02` |
| `Temperature` | `3bf3d02` |
| `TemperatureCompensationDisabled` | `3c23d02` |
| `UpTime` | `3c33d02` |
| `Version` | `2e23d02` |
| `VersionBugfix` | `2e03d02` |
| `VersionBuild` | `2e13d02` |
| `VersionMajor` | `2de3d02` |
| `VersionMinor` | `2df3d02` |
| `Yaw` | `3b53d02` |

#### `TalonFX-1`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0100` |
| `AncillaryDeviceTemp` | `82b0100` |
| `AppliedRotorPolarity` | `6ef0100` |
| `BridgeOutput` | `7ab0100` |
| `ClosedLoopSlot` | `7220100` |
| `ConnectedMotor` | `8450100` |
| `ControlMode` | `7070100` |
| `DeviceEnable` | `7100100` |
| `DeviceTemp` | `6f60100` |
| `DutyCycle` | `6f00100` |
| `FaultField` | `34c0100` |
| `Fault_BootDuringEnable` | `271d0100` |
| `Fault_BridgeBrownout` | `27410100` |
| `Fault_DeviceTemp` | `27170100` |
| `Fault_ForwardHardLimit` | `27560100` |
| `Fault_ForwardSoftLimit` | `275c0100` |
| `Fault_FusedSensorOutOfSync` | `27680100` |
| `Fault_Hardware` | `27110100` |
| `Fault_MissingDifferentialFX` | `27470100` |
| `Fault_MissingHardLimitRemote` | `27620100` |
| `Fault_MissingSoftLimitRemote` | `275f0100` |
| `Fault_OverSupplyV` | `274d0100` |
| `Fault_ProcTemp` | `27140100` |
| `Fault_RemoteSensorDataInvalid` | `27650100` |
| `Fault_RemoteSensorPosOverflow` | `274a0100` |
| `Fault_RemoteSensorReset` | `27440100` |
| `Fault_ReverseHardLimit` | `27530100` |
| `Fault_ReverseSoftLimit` | `27590100` |
| `Fault_RotorFault1` | `27a10100` |
| `Fault_RotorFault2` | `27a40100` |
| `Fault_StaticBrakeDisabled` | `27740100` |
| `Fault_StatorCurrLimit` | `276b0100` |
| `Fault_SupplyCurrLimit` | `276e0100` |
| `Fault_Undervoltage` | `271a0100` |
| `Fault_UnlicensedFeatureInUse` | `27200100` |
| `Fault_UnstableSupplyV` | `27500100` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710100` |
| `ForwardLimit` | `6ed0100` |
| `IsProLicensed` | `8040100` |
| `MotionMagicAtTarget` | `70d0100` |
| `MotionMagicIsRunning` | `70e0100` |
| `MotorKT` | `7520100` |
| `MotorKV` | `7530100` |
| `MotorOutputStatus` | `7260100` |
| `MotorStallCurrent` | `7540100` |
| `MotorVoltage` | `6ec0100` |
| `PIDDutyCycle_DerivativeOutput` | `71c0100` |
| `PIDDutyCycle_FeedForward` | `7040100` |
| `PIDDutyCycle_IntegratedAccum` | `7010100` |
| `PIDDutyCycle_Output` | `71f0100` |
| `PIDDutyCycle_ProportionalOutput` | `7190100` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0100` |
| `PIDMotorVoltage_FeedForward` | `7050100` |
| `PIDMotorVoltage_IntegratedAccum` | `7020100` |
| `PIDMotorVoltage_Output` | `7200100` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0100` |
| `PIDPosition_ClosedLoopError` | `7140100` |
| `PIDPosition_Reference` | `7120100` |
| `PIDPosition_ReferenceSlope` | `7230100` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0100` |
| `PIDTorqueCurrent_FeedForward` | `7060100` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030100` |
| `PIDTorqueCurrent_Output` | `7210100` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0100` |
| `PIDVelocity_ClosedLoopError` | `7150100` |
| `PIDVelocity_Reference` | `7130100` |
| `PIDVelocity_ReferenceSlope` | `7240100` |
| `Position` | `6fe0100` |
| `ProcessorTemp` | `6f70100` |
| `ReverseLimit` | `6ee0100` |
| `RobotEnable` | `70f0100` |
| `RotorPosition` | `6fa0100` |
| `RotorVelocity` | `6f90100` |
| `StatorCurrent` | `6f30100` |
| `StickyFaultField` | `34d0100` |
| `StickyFault_BootDuringEnable` | `271e0100` |
| `StickyFault_BridgeBrownout` | `27420100` |
| `StickyFault_DeviceTemp` | `27180100` |
| `StickyFault_ForwardHardLimit` | `27570100` |
| `StickyFault_ForwardSoftLimit` | `275d0100` |
| `StickyFault_FusedSensorOutOfSync` | `27690100` |
| `StickyFault_Hardware` | `27120100` |
| `StickyFault_MissingDifferentialFX` | `27480100` |
| `StickyFault_MissingHardLimitRemote` | `27630100` |
| `StickyFault_MissingSoftLimitRemote` | `27600100` |
| `StickyFault_OverSupplyV` | `274e0100` |
| `StickyFault_ProcTemp` | `27150100` |
| `StickyFault_RemoteSensorDataInvalid` | `27660100` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0100` |
| `StickyFault_RemoteSensorReset` | `27450100` |
| `StickyFault_ReverseHardLimit` | `27540100` |
| `StickyFault_ReverseSoftLimit` | `275a0100` |
| `StickyFault_RotorFault1` | `27a20100` |
| `StickyFault_RotorFault2` | `27a50100` |
| `StickyFault_StaticBrakeDisabled` | `27750100` |
| `StickyFault_StatorCurrLimit` | `276c0100` |
| `StickyFault_SupplyCurrLimit` | `276f0100` |
| `StickyFault_Undervoltage` | `271b0100` |
| `StickyFault_UnlicensedFeatureInUse` | `27210100` |
| `StickyFault_UnstableSupplyV` | `27510100` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720100` |
| `SupplyCurrent` | `6f40100` |
| `SupplyVoltage` | `6f50100` |
| `TorqueCurrent` | `6f20100` |
| `Velocity` | `6fd0100` |
| `Version` | `2e20100` |
| `VersionBugfix` | `2e00100` |
| `VersionBuild` | `2e10100` |
| `VersionMajor` | `2de0100` |
| `VersionMinor` | `2df0100` |

#### `TalonFX-11`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0b00` |
| `AncillaryDeviceTemp` | `82b0b00` |
| `AppliedRotorPolarity` | `6ef0b00` |
| `BridgeOutput` | `7ab0b00` |
| `ClosedLoopSlot` | `7220b00` |
| `ConnectedMotor` | `8450b00` |
| `ControlMode` | `7070b00` |
| `DeviceEnable` | `7100b00` |
| `DeviceTemp` | `6f60b00` |
| `DutyCycle` | `6f00b00` |
| `FaultField` | `34c0b00` |
| `Fault_BootDuringEnable` | `271d0b00` |
| `Fault_BridgeBrownout` | `27410b00` |
| `Fault_DeviceTemp` | `27170b00` |
| `Fault_ForwardHardLimit` | `27560b00` |
| `Fault_ForwardSoftLimit` | `275c0b00` |
| `Fault_FusedSensorOutOfSync` | `27680b00` |
| `Fault_Hardware` | `27110b00` |
| `Fault_MissingDifferentialFX` | `27470b00` |
| `Fault_MissingHardLimitRemote` | `27620b00` |
| `Fault_MissingSoftLimitRemote` | `275f0b00` |
| `Fault_OverSupplyV` | `274d0b00` |
| `Fault_ProcTemp` | `27140b00` |
| `Fault_RemoteSensorDataInvalid` | `27650b00` |
| `Fault_RemoteSensorPosOverflow` | `274a0b00` |
| `Fault_RemoteSensorReset` | `27440b00` |
| `Fault_ReverseHardLimit` | `27530b00` |
| `Fault_ReverseSoftLimit` | `27590b00` |
| `Fault_RotorFault1` | `27a10b00` |
| `Fault_RotorFault2` | `27a40b00` |
| `Fault_StaticBrakeDisabled` | `27740b00` |
| `Fault_StatorCurrLimit` | `276b0b00` |
| `Fault_SupplyCurrLimit` | `276e0b00` |
| `Fault_Undervoltage` | `271a0b00` |
| `Fault_UnlicensedFeatureInUse` | `27200b00` |
| `Fault_UnstableSupplyV` | `27500b00` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710b00` |
| `ForwardLimit` | `6ed0b00` |
| `IsProLicensed` | `8040b00` |
| `MotionMagicAtTarget` | `70d0b00` |
| `MotionMagicIsRunning` | `70e0b00` |
| `MotorKT` | `7520b00` |
| `MotorKV` | `7530b00` |
| `MotorOutputStatus` | `7260b00` |
| `MotorStallCurrent` | `7540b00` |
| `MotorVoltage` | `6ec0b00` |
| `PIDDutyCycle_DerivativeOutput` | `71c0b00` |
| `PIDDutyCycle_FeedForward` | `7040b00` |
| `PIDDutyCycle_IntegratedAccum` | `7010b00` |
| `PIDDutyCycle_Output` | `71f0b00` |
| `PIDDutyCycle_ProportionalOutput` | `7190b00` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0b00` |
| `PIDMotorVoltage_FeedForward` | `7050b00` |
| `PIDMotorVoltage_IntegratedAccum` | `7020b00` |
| `PIDMotorVoltage_Output` | `7200b00` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0b00` |
| `PIDPosition_ClosedLoopError` | `7140b00` |
| `PIDPosition_Reference` | `7120b00` |
| `PIDPosition_ReferenceSlope` | `7230b00` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0b00` |
| `PIDTorqueCurrent_FeedForward` | `7060b00` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030b00` |
| `PIDTorqueCurrent_Output` | `7210b00` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0b00` |
| `PIDVelocity_ClosedLoopError` | `7150b00` |
| `PIDVelocity_Reference` | `7130b00` |
| `PIDVelocity_ReferenceSlope` | `7240b00` |
| `Position` | `6fe0b00` |
| `ProcessorTemp` | `6f70b00` |
| `ReverseLimit` | `6ee0b00` |
| `RobotEnable` | `70f0b00` |
| `RotorPosition` | `6fa0b00` |
| `RotorVelocity` | `6f90b00` |
| `StatorCurrent` | `6f30b00` |
| `StickyFaultField` | `34d0b00` |
| `StickyFault_BootDuringEnable` | `271e0b00` |
| `StickyFault_BridgeBrownout` | `27420b00` |
| `StickyFault_DeviceTemp` | `27180b00` |
| `StickyFault_ForwardHardLimit` | `27570b00` |
| `StickyFault_ForwardSoftLimit` | `275d0b00` |
| `StickyFault_FusedSensorOutOfSync` | `27690b00` |
| `StickyFault_Hardware` | `27120b00` |
| `StickyFault_MissingDifferentialFX` | `27480b00` |
| `StickyFault_MissingHardLimitRemote` | `27630b00` |
| `StickyFault_MissingSoftLimitRemote` | `27600b00` |
| `StickyFault_OverSupplyV` | `274e0b00` |
| `StickyFault_ProcTemp` | `27150b00` |
| `StickyFault_RemoteSensorDataInvalid` | `27660b00` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0b00` |
| `StickyFault_RemoteSensorReset` | `27450b00` |
| `StickyFault_ReverseHardLimit` | `27540b00` |
| `StickyFault_ReverseSoftLimit` | `275a0b00` |
| `StickyFault_RotorFault1` | `27a20b00` |
| `StickyFault_RotorFault2` | `27a50b00` |
| `StickyFault_StaticBrakeDisabled` | `27750b00` |
| `StickyFault_StatorCurrLimit` | `276c0b00` |
| `StickyFault_SupplyCurrLimit` | `276f0b00` |
| `StickyFault_Undervoltage` | `271b0b00` |
| `StickyFault_UnlicensedFeatureInUse` | `27210b00` |
| `StickyFault_UnstableSupplyV` | `27510b00` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720b00` |
| `SupplyCurrent` | `6f40b00` |
| `SupplyVoltage` | `6f50b00` |
| `TorqueCurrent` | `6f20b00` |
| `Velocity` | `6fd0b00` |
| `Version` | `2e20b00` |
| `VersionBugfix` | `2e00b00` |
| `VersionBuild` | `2e10b00` |
| `VersionMajor` | `2de0b00` |
| `VersionMinor` | `2df0b00` |

#### `TalonFX-2`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0200` |
| `AncillaryDeviceTemp` | `82b0200` |
| `AppliedRotorPolarity` | `6ef0200` |
| `BridgeOutput` | `7ab0200` |
| `ClosedLoopSlot` | `7220200` |
| `ConnectedMotor` | `8450200` |
| `ControlMode` | `7070200` |
| `DeviceEnable` | `7100200` |
| `DeviceTemp` | `6f60200` |
| `DutyCycle` | `6f00200` |
| `FaultField` | `34c0200` |
| `Fault_BootDuringEnable` | `271d0200` |
| `Fault_BridgeBrownout` | `27410200` |
| `Fault_DeviceTemp` | `27170200` |
| `Fault_ForwardHardLimit` | `27560200` |
| `Fault_ForwardSoftLimit` | `275c0200` |
| `Fault_FusedSensorOutOfSync` | `27680200` |
| `Fault_Hardware` | `27110200` |
| `Fault_MissingDifferentialFX` | `27470200` |
| `Fault_MissingHardLimitRemote` | `27620200` |
| `Fault_MissingSoftLimitRemote` | `275f0200` |
| `Fault_OverSupplyV` | `274d0200` |
| `Fault_ProcTemp` | `27140200` |
| `Fault_RemoteSensorDataInvalid` | `27650200` |
| `Fault_RemoteSensorPosOverflow` | `274a0200` |
| `Fault_RemoteSensorReset` | `27440200` |
| `Fault_ReverseHardLimit` | `27530200` |
| `Fault_ReverseSoftLimit` | `27590200` |
| `Fault_RotorFault1` | `27a10200` |
| `Fault_RotorFault2` | `27a40200` |
| `Fault_StaticBrakeDisabled` | `27740200` |
| `Fault_StatorCurrLimit` | `276b0200` |
| `Fault_SupplyCurrLimit` | `276e0200` |
| `Fault_Undervoltage` | `271a0200` |
| `Fault_UnlicensedFeatureInUse` | `27200200` |
| `Fault_UnstableSupplyV` | `27500200` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710200` |
| `ForwardLimit` | `6ed0200` |
| `IsProLicensed` | `8040200` |
| `MotionMagicAtTarget` | `70d0200` |
| `MotionMagicIsRunning` | `70e0200` |
| `MotorKT` | `7520200` |
| `MotorKV` | `7530200` |
| `MotorOutputStatus` | `7260200` |
| `MotorStallCurrent` | `7540200` |
| `MotorVoltage` | `6ec0200` |
| `PIDDutyCycle_DerivativeOutput` | `71c0200` |
| `PIDDutyCycle_FeedForward` | `7040200` |
| `PIDDutyCycle_IntegratedAccum` | `7010200` |
| `PIDDutyCycle_Output` | `71f0200` |
| `PIDDutyCycle_ProportionalOutput` | `7190200` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0200` |
| `PIDMotorVoltage_FeedForward` | `7050200` |
| `PIDMotorVoltage_IntegratedAccum` | `7020200` |
| `PIDMotorVoltage_Output` | `7200200` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0200` |
| `PIDPosition_ClosedLoopError` | `7140200` |
| `PIDPosition_Reference` | `7120200` |
| `PIDPosition_ReferenceSlope` | `7230200` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0200` |
| `PIDTorqueCurrent_FeedForward` | `7060200` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030200` |
| `PIDTorqueCurrent_Output` | `7210200` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0200` |
| `PIDVelocity_ClosedLoopError` | `7150200` |
| `PIDVelocity_Reference` | `7130200` |
| `PIDVelocity_ReferenceSlope` | `7240200` |
| `Position` | `6fe0200` |
| `ProcessorTemp` | `6f70200` |
| `ReverseLimit` | `6ee0200` |
| `RobotEnable` | `70f0200` |
| `RotorPosition` | `6fa0200` |
| `RotorVelocity` | `6f90200` |
| `StatorCurrent` | `6f30200` |
| `StickyFaultField` | `34d0200` |
| `StickyFault_BootDuringEnable` | `271e0200` |
| `StickyFault_BridgeBrownout` | `27420200` |
| `StickyFault_DeviceTemp` | `27180200` |
| `StickyFault_ForwardHardLimit` | `27570200` |
| `StickyFault_ForwardSoftLimit` | `275d0200` |
| `StickyFault_FusedSensorOutOfSync` | `27690200` |
| `StickyFault_Hardware` | `27120200` |
| `StickyFault_MissingDifferentialFX` | `27480200` |
| `StickyFault_MissingHardLimitRemote` | `27630200` |
| `StickyFault_MissingSoftLimitRemote` | `27600200` |
| `StickyFault_OverSupplyV` | `274e0200` |
| `StickyFault_ProcTemp` | `27150200` |
| `StickyFault_RemoteSensorDataInvalid` | `27660200` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0200` |
| `StickyFault_RemoteSensorReset` | `27450200` |
| `StickyFault_ReverseHardLimit` | `27540200` |
| `StickyFault_ReverseSoftLimit` | `275a0200` |
| `StickyFault_RotorFault1` | `27a20200` |
| `StickyFault_RotorFault2` | `27a50200` |
| `StickyFault_StaticBrakeDisabled` | `27750200` |
| `StickyFault_StatorCurrLimit` | `276c0200` |
| `StickyFault_SupplyCurrLimit` | `276f0200` |
| `StickyFault_Undervoltage` | `271b0200` |
| `StickyFault_UnlicensedFeatureInUse` | `27210200` |
| `StickyFault_UnstableSupplyV` | `27510200` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720200` |
| `SupplyCurrent` | `6f40200` |
| `SupplyVoltage` | `6f50200` |
| `TorqueCurrent` | `6f20200` |
| `Velocity` | `6fd0200` |
| `Version` | `2e20200` |
| `VersionBugfix` | `2e00200` |
| `VersionBuild` | `2e10200` |
| `VersionMajor` | `2de0200` |
| `VersionMinor` | `2df0200` |

#### `TalonFX-3`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0300` |
| `AncillaryDeviceTemp` | `82b0300` |
| `AppliedRotorPolarity` | `6ef0300` |
| `BridgeOutput` | `7ab0300` |
| `ClosedLoopSlot` | `7220300` |
| `ConnectedMotor` | `8450300` |
| `ControlMode` | `7070300` |
| `DeviceEnable` | `7100300` |
| `DeviceTemp` | `6f60300` |
| `DutyCycle` | `6f00300` |
| `FaultField` | `34c0300` |
| `Fault_BootDuringEnable` | `271d0300` |
| `Fault_BridgeBrownout` | `27410300` |
| `Fault_DeviceTemp` | `27170300` |
| `Fault_ForwardHardLimit` | `27560300` |
| `Fault_ForwardSoftLimit` | `275c0300` |
| `Fault_FusedSensorOutOfSync` | `27680300` |
| `Fault_Hardware` | `27110300` |
| `Fault_MissingDifferentialFX` | `27470300` |
| `Fault_MissingHardLimitRemote` | `27620300` |
| `Fault_MissingSoftLimitRemote` | `275f0300` |
| `Fault_OverSupplyV` | `274d0300` |
| `Fault_ProcTemp` | `27140300` |
| `Fault_RemoteSensorDataInvalid` | `27650300` |
| `Fault_RemoteSensorPosOverflow` | `274a0300` |
| `Fault_RemoteSensorReset` | `27440300` |
| `Fault_ReverseHardLimit` | `27530300` |
| `Fault_ReverseSoftLimit` | `27590300` |
| `Fault_RotorFault1` | `27a10300` |
| `Fault_RotorFault2` | `27a40300` |
| `Fault_StaticBrakeDisabled` | `27740300` |
| `Fault_StatorCurrLimit` | `276b0300` |
| `Fault_SupplyCurrLimit` | `276e0300` |
| `Fault_Undervoltage` | `271a0300` |
| `Fault_UnlicensedFeatureInUse` | `27200300` |
| `Fault_UnstableSupplyV` | `27500300` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710300` |
| `ForwardLimit` | `6ed0300` |
| `IsProLicensed` | `8040300` |
| `MotionMagicAtTarget` | `70d0300` |
| `MotionMagicIsRunning` | `70e0300` |
| `MotorKT` | `7520300` |
| `MotorKV` | `7530300` |
| `MotorOutputStatus` | `7260300` |
| `MotorStallCurrent` | `7540300` |
| `MotorVoltage` | `6ec0300` |
| `PIDDutyCycle_DerivativeOutput` | `71c0300` |
| `PIDDutyCycle_FeedForward` | `7040300` |
| `PIDDutyCycle_IntegratedAccum` | `7010300` |
| `PIDDutyCycle_Output` | `71f0300` |
| `PIDDutyCycle_ProportionalOutput` | `7190300` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0300` |
| `PIDMotorVoltage_FeedForward` | `7050300` |
| `PIDMotorVoltage_IntegratedAccum` | `7020300` |
| `PIDMotorVoltage_Output` | `7200300` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0300` |
| `PIDPosition_ClosedLoopError` | `7140300` |
| `PIDPosition_Reference` | `7120300` |
| `PIDPosition_ReferenceSlope` | `7230300` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0300` |
| `PIDTorqueCurrent_FeedForward` | `7060300` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030300` |
| `PIDTorqueCurrent_Output` | `7210300` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0300` |
| `PIDVelocity_ClosedLoopError` | `7150300` |
| `PIDVelocity_Reference` | `7130300` |
| `PIDVelocity_ReferenceSlope` | `7240300` |
| `Position` | `6fe0300` |
| `ProcessorTemp` | `6f70300` |
| `ReverseLimit` | `6ee0300` |
| `RobotEnable` | `70f0300` |
| `RotorPosition` | `6fa0300` |
| `RotorVelocity` | `6f90300` |
| `StatorCurrent` | `6f30300` |
| `StickyFaultField` | `34d0300` |
| `StickyFault_BootDuringEnable` | `271e0300` |
| `StickyFault_BridgeBrownout` | `27420300` |
| `StickyFault_DeviceTemp` | `27180300` |
| `StickyFault_ForwardHardLimit` | `27570300` |
| `StickyFault_ForwardSoftLimit` | `275d0300` |
| `StickyFault_FusedSensorOutOfSync` | `27690300` |
| `StickyFault_Hardware` | `27120300` |
| `StickyFault_MissingDifferentialFX` | `27480300` |
| `StickyFault_MissingHardLimitRemote` | `27630300` |
| `StickyFault_MissingSoftLimitRemote` | `27600300` |
| `StickyFault_OverSupplyV` | `274e0300` |
| `StickyFault_ProcTemp` | `27150300` |
| `StickyFault_RemoteSensorDataInvalid` | `27660300` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0300` |
| `StickyFault_RemoteSensorReset` | `27450300` |
| `StickyFault_ReverseHardLimit` | `27540300` |
| `StickyFault_ReverseSoftLimit` | `275a0300` |
| `StickyFault_RotorFault1` | `27a20300` |
| `StickyFault_RotorFault2` | `27a50300` |
| `StickyFault_StaticBrakeDisabled` | `27750300` |
| `StickyFault_StatorCurrLimit` | `276c0300` |
| `StickyFault_SupplyCurrLimit` | `276f0300` |
| `StickyFault_Undervoltage` | `271b0300` |
| `StickyFault_UnlicensedFeatureInUse` | `27210300` |
| `StickyFault_UnstableSupplyV` | `27510300` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720300` |
| `SupplyCurrent` | `6f40300` |
| `SupplyVoltage` | `6f50300` |
| `TorqueCurrent` | `6f20300` |
| `Velocity` | `6fd0300` |
| `Version` | `2e20300` |
| `VersionBugfix` | `2e00300` |
| `VersionBuild` | `2e10300` |
| `VersionMajor` | `2de0300` |
| `VersionMinor` | `2df0300` |

#### `TalonFX-30`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff1e00` |
| `AncillaryDeviceTemp` | `82b1e00` |
| `AppliedRotorPolarity` | `6ef1e00` |
| `BridgeOutput` | `7ab1e00` |
| `ClosedLoopSlot` | `7221e00` |
| `ConnectedMotor` | `8451e00` |
| `ControlMode` | `7071e00` |
| `DeviceEnable` | `7101e00` |
| `DeviceTemp` | `6f61e00` |
| `DutyCycle` | `6f01e00` |
| `FaultField` | `34c1e00` |
| `Fault_BootDuringEnable` | `271d1e00` |
| `Fault_BridgeBrownout` | `27411e00` |
| `Fault_DeviceTemp` | `27171e00` |
| `Fault_ForwardHardLimit` | `27561e00` |
| `Fault_ForwardSoftLimit` | `275c1e00` |
| `Fault_FusedSensorOutOfSync` | `27681e00` |
| `Fault_Hardware` | `27111e00` |
| `Fault_MissingDifferentialFX` | `27471e00` |
| `Fault_MissingHardLimitRemote` | `27621e00` |
| `Fault_MissingSoftLimitRemote` | `275f1e00` |
| `Fault_OverSupplyV` | `274d1e00` |
| `Fault_ProcTemp` | `27141e00` |
| `Fault_RemoteSensorDataInvalid` | `27651e00` |
| `Fault_RemoteSensorPosOverflow` | `274a1e00` |
| `Fault_RemoteSensorReset` | `27441e00` |
| `Fault_ReverseHardLimit` | `27531e00` |
| `Fault_ReverseSoftLimit` | `27591e00` |
| `Fault_RotorFault1` | `27a11e00` |
| `Fault_RotorFault2` | `27a41e00` |
| `Fault_StaticBrakeDisabled` | `27741e00` |
| `Fault_StatorCurrLimit` | `276b1e00` |
| `Fault_SupplyCurrLimit` | `276e1e00` |
| `Fault_Undervoltage` | `271a1e00` |
| `Fault_UnlicensedFeatureInUse` | `27201e00` |
| `Fault_UnstableSupplyV` | `27501e00` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27711e00` |
| `ForwardLimit` | `6ed1e00` |
| `IsProLicensed` | `8041e00` |
| `MotionMagicAtTarget` | `70d1e00` |
| `MotionMagicIsRunning` | `70e1e00` |
| `MotorKT` | `7521e00` |
| `MotorKV` | `7531e00` |
| `MotorOutputStatus` | `7261e00` |
| `MotorStallCurrent` | `7541e00` |
| `MotorVoltage` | `6ec1e00` |
| `PIDDutyCycle_DerivativeOutput` | `71c1e00` |
| `PIDDutyCycle_FeedForward` | `7041e00` |
| `PIDDutyCycle_IntegratedAccum` | `7011e00` |
| `PIDDutyCycle_Output` | `71f1e00` |
| `PIDDutyCycle_ProportionalOutput` | `7191e00` |
| `PIDMotorVoltage_DerivativeOutput` | `71d1e00` |
| `PIDMotorVoltage_FeedForward` | `7051e00` |
| `PIDMotorVoltage_IntegratedAccum` | `7021e00` |
| `PIDMotorVoltage_Output` | `7201e00` |
| `PIDMotorVoltage_ProportionalOutput` | `71a1e00` |
| `PIDPosition_ClosedLoopError` | `7141e00` |
| `PIDPosition_Reference` | `7121e00` |
| `PIDPosition_ReferenceSlope` | `7231e00` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e1e00` |
| `PIDTorqueCurrent_FeedForward` | `7061e00` |
| `PIDTorqueCurrent_IntegratedAccum` | `7031e00` |
| `PIDTorqueCurrent_Output` | `7211e00` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b1e00` |
| `PIDVelocity_ClosedLoopError` | `7151e00` |
| `PIDVelocity_Reference` | `7131e00` |
| `PIDVelocity_ReferenceSlope` | `7241e00` |
| `Position` | `6fe1e00` |
| `ProcessorTemp` | `6f71e00` |
| `ReverseLimit` | `6ee1e00` |
| `RobotEnable` | `70f1e00` |
| `RotorPosition` | `6fa1e00` |
| `RotorVelocity` | `6f91e00` |
| `StatorCurrent` | `6f31e00` |
| `StickyFaultField` | `34d1e00` |
| `StickyFault_BootDuringEnable` | `271e1e00` |
| `StickyFault_BridgeBrownout` | `27421e00` |
| `StickyFault_DeviceTemp` | `27181e00` |
| `StickyFault_ForwardHardLimit` | `27571e00` |
| `StickyFault_ForwardSoftLimit` | `275d1e00` |
| `StickyFault_FusedSensorOutOfSync` | `27691e00` |
| `StickyFault_Hardware` | `27121e00` |
| `StickyFault_MissingDifferentialFX` | `27481e00` |
| `StickyFault_MissingHardLimitRemote` | `27631e00` |
| `StickyFault_MissingSoftLimitRemote` | `27601e00` |
| `StickyFault_OverSupplyV` | `274e1e00` |
| `StickyFault_ProcTemp` | `27151e00` |
| `StickyFault_RemoteSensorDataInvalid` | `27661e00` |
| `StickyFault_RemoteSensorPosOverflow` | `274b1e00` |
| `StickyFault_RemoteSensorReset` | `27451e00` |
| `StickyFault_ReverseHardLimit` | `27541e00` |
| `StickyFault_ReverseSoftLimit` | `275a1e00` |
| `StickyFault_RotorFault1` | `27a21e00` |
| `StickyFault_RotorFault2` | `27a51e00` |
| `StickyFault_StaticBrakeDisabled` | `27751e00` |
| `StickyFault_StatorCurrLimit` | `276c1e00` |
| `StickyFault_SupplyCurrLimit` | `276f1e00` |
| `StickyFault_Undervoltage` | `271b1e00` |
| `StickyFault_UnlicensedFeatureInUse` | `27211e00` |
| `StickyFault_UnstableSupplyV` | `27511e00` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27721e00` |
| `SupplyCurrent` | `6f41e00` |
| `SupplyVoltage` | `6f51e00` |
| `TorqueCurrent` | `6f21e00` |
| `Velocity` | `6fd1e00` |
| `Version` | `2e21e00` |
| `VersionBugfix` | `2e01e00` |
| `VersionBuild` | `2e11e00` |
| `VersionMajor` | `2de1e00` |
| `VersionMinor` | `2df1e00` |

#### `TalonFX-31`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff1f00` |
| `AncillaryDeviceTemp` | `82b1f00` |
| `AppliedRotorPolarity` | `6ef1f00` |
| `BridgeOutput` | `7ab1f00` |
| `ClosedLoopSlot` | `7221f00` |
| `ConnectedMotor` | `8451f00` |
| `ControlMode` | `7071f00` |
| `DeviceEnable` | `7101f00` |
| `DeviceTemp` | `6f61f00` |
| `DutyCycle` | `6f01f00` |
| `FaultField` | `34c1f00` |
| `Fault_BootDuringEnable` | `271d1f00` |
| `Fault_BridgeBrownout` | `27411f00` |
| `Fault_DeviceTemp` | `27171f00` |
| `Fault_ForwardHardLimit` | `27561f00` |
| `Fault_ForwardSoftLimit` | `275c1f00` |
| `Fault_FusedSensorOutOfSync` | `27681f00` |
| `Fault_Hardware` | `27111f00` |
| `Fault_MissingDifferentialFX` | `27471f00` |
| `Fault_MissingHardLimitRemote` | `27621f00` |
| `Fault_MissingSoftLimitRemote` | `275f1f00` |
| `Fault_OverSupplyV` | `274d1f00` |
| `Fault_ProcTemp` | `27141f00` |
| `Fault_RemoteSensorDataInvalid` | `27651f00` |
| `Fault_RemoteSensorPosOverflow` | `274a1f00` |
| `Fault_RemoteSensorReset` | `27441f00` |
| `Fault_ReverseHardLimit` | `27531f00` |
| `Fault_ReverseSoftLimit` | `27591f00` |
| `Fault_RotorFault1` | `27a11f00` |
| `Fault_RotorFault2` | `27a41f00` |
| `Fault_StaticBrakeDisabled` | `27741f00` |
| `Fault_StatorCurrLimit` | `276b1f00` |
| `Fault_SupplyCurrLimit` | `276e1f00` |
| `Fault_Undervoltage` | `271a1f00` |
| `Fault_UnlicensedFeatureInUse` | `27201f00` |
| `Fault_UnstableSupplyV` | `27501f00` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27711f00` |
| `ForwardLimit` | `6ed1f00` |
| `IsProLicensed` | `8041f00` |
| `MotionMagicAtTarget` | `70d1f00` |
| `MotionMagicIsRunning` | `70e1f00` |
| `MotorKT` | `7521f00` |
| `MotorKV` | `7531f00` |
| `MotorOutputStatus` | `7261f00` |
| `MotorStallCurrent` | `7541f00` |
| `MotorVoltage` | `6ec1f00` |
| `PIDDutyCycle_DerivativeOutput` | `71c1f00` |
| `PIDDutyCycle_FeedForward` | `7041f00` |
| `PIDDutyCycle_IntegratedAccum` | `7011f00` |
| `PIDDutyCycle_Output` | `71f1f00` |
| `PIDDutyCycle_ProportionalOutput` | `7191f00` |
| `PIDMotorVoltage_DerivativeOutput` | `71d1f00` |
| `PIDMotorVoltage_FeedForward` | `7051f00` |
| `PIDMotorVoltage_IntegratedAccum` | `7021f00` |
| `PIDMotorVoltage_Output` | `7201f00` |
| `PIDMotorVoltage_ProportionalOutput` | `71a1f00` |
| `PIDPosition_ClosedLoopError` | `7141f00` |
| `PIDPosition_Reference` | `7121f00` |
| `PIDPosition_ReferenceSlope` | `7231f00` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e1f00` |
| `PIDTorqueCurrent_FeedForward` | `7061f00` |
| `PIDTorqueCurrent_IntegratedAccum` | `7031f00` |
| `PIDTorqueCurrent_Output` | `7211f00` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b1f00` |
| `PIDVelocity_ClosedLoopError` | `7151f00` |
| `PIDVelocity_Reference` | `7131f00` |
| `PIDVelocity_ReferenceSlope` | `7241f00` |
| `Position` | `6fe1f00` |
| `ProcessorTemp` | `6f71f00` |
| `ReverseLimit` | `6ee1f00` |
| `RobotEnable` | `70f1f00` |
| `RotorPosition` | `6fa1f00` |
| `RotorVelocity` | `6f91f00` |
| `StatorCurrent` | `6f31f00` |
| `StickyFaultField` | `34d1f00` |
| `StickyFault_BootDuringEnable` | `271e1f00` |
| `StickyFault_BridgeBrownout` | `27421f00` |
| `StickyFault_DeviceTemp` | `27181f00` |
| `StickyFault_ForwardHardLimit` | `27571f00` |
| `StickyFault_ForwardSoftLimit` | `275d1f00` |
| `StickyFault_FusedSensorOutOfSync` | `27691f00` |
| `StickyFault_Hardware` | `27121f00` |
| `StickyFault_MissingDifferentialFX` | `27481f00` |
| `StickyFault_MissingHardLimitRemote` | `27631f00` |
| `StickyFault_MissingSoftLimitRemote` | `27601f00` |
| `StickyFault_OverSupplyV` | `274e1f00` |
| `StickyFault_ProcTemp` | `27151f00` |
| `StickyFault_RemoteSensorDataInvalid` | `27661f00` |
| `StickyFault_RemoteSensorPosOverflow` | `274b1f00` |
| `StickyFault_RemoteSensorReset` | `27451f00` |
| `StickyFault_ReverseHardLimit` | `27541f00` |
| `StickyFault_ReverseSoftLimit` | `275a1f00` |
| `StickyFault_RotorFault1` | `27a21f00` |
| `StickyFault_RotorFault2` | `27a51f00` |
| `StickyFault_StaticBrakeDisabled` | `27751f00` |
| `StickyFault_StatorCurrLimit` | `276c1f00` |
| `StickyFault_SupplyCurrLimit` | `276f1f00` |
| `StickyFault_Undervoltage` | `271b1f00` |
| `StickyFault_UnlicensedFeatureInUse` | `27211f00` |
| `StickyFault_UnstableSupplyV` | `27511f00` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27721f00` |
| `SupplyCurrent` | `6f41f00` |
| `SupplyVoltage` | `6f51f00` |
| `TorqueCurrent` | `6f21f00` |
| `Velocity` | `6fd1f00` |
| `Version` | `2e21f00` |
| `VersionBugfix` | `2e01f00` |
| `VersionBuild` | `2e11f00` |
| `VersionMajor` | `2de1f00` |
| `VersionMinor` | `2df1f00` |

#### `TalonFX-32`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff2000` |
| `AncillaryDeviceTemp` | `82b2000` |
| `AppliedRotorPolarity` | `6ef2000` |
| `BridgeOutput` | `7ab2000` |
| `ClosedLoopSlot` | `7222000` |
| `ConnectedMotor` | `8452000` |
| `ControlMode` | `7072000` |
| `DeviceEnable` | `7102000` |
| `DeviceTemp` | `6f62000` |
| `DutyCycle` | `6f02000` |
| `FaultField` | `34c2000` |
| `Fault_BootDuringEnable` | `271d2000` |
| `Fault_BridgeBrownout` | `27412000` |
| `Fault_DeviceTemp` | `27172000` |
| `Fault_ForwardHardLimit` | `27562000` |
| `Fault_ForwardSoftLimit` | `275c2000` |
| `Fault_FusedSensorOutOfSync` | `27682000` |
| `Fault_Hardware` | `27112000` |
| `Fault_MissingDifferentialFX` | `27472000` |
| `Fault_MissingHardLimitRemote` | `27622000` |
| `Fault_MissingSoftLimitRemote` | `275f2000` |
| `Fault_OverSupplyV` | `274d2000` |
| `Fault_ProcTemp` | `27142000` |
| `Fault_RemoteSensorDataInvalid` | `27652000` |
| `Fault_RemoteSensorPosOverflow` | `274a2000` |
| `Fault_RemoteSensorReset` | `27442000` |
| `Fault_ReverseHardLimit` | `27532000` |
| `Fault_ReverseSoftLimit` | `27592000` |
| `Fault_RotorFault1` | `27a12000` |
| `Fault_RotorFault2` | `27a42000` |
| `Fault_StaticBrakeDisabled` | `27742000` |
| `Fault_StatorCurrLimit` | `276b2000` |
| `Fault_SupplyCurrLimit` | `276e2000` |
| `Fault_Undervoltage` | `271a2000` |
| `Fault_UnlicensedFeatureInUse` | `27202000` |
| `Fault_UnstableSupplyV` | `27502000` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27712000` |
| `ForwardLimit` | `6ed2000` |
| `IsProLicensed` | `8042000` |
| `MotionMagicAtTarget` | `70d2000` |
| `MotionMagicIsRunning` | `70e2000` |
| `MotorKT` | `7522000` |
| `MotorKV` | `7532000` |
| `MotorOutputStatus` | `7262000` |
| `MotorStallCurrent` | `7542000` |
| `MotorVoltage` | `6ec2000` |
| `PIDDutyCycle_DerivativeOutput` | `71c2000` |
| `PIDDutyCycle_FeedForward` | `7042000` |
| `PIDDutyCycle_IntegratedAccum` | `7012000` |
| `PIDDutyCycle_Output` | `71f2000` |
| `PIDDutyCycle_ProportionalOutput` | `7192000` |
| `PIDMotorVoltage_DerivativeOutput` | `71d2000` |
| `PIDMotorVoltage_FeedForward` | `7052000` |
| `PIDMotorVoltage_IntegratedAccum` | `7022000` |
| `PIDMotorVoltage_Output` | `7202000` |
| `PIDMotorVoltage_ProportionalOutput` | `71a2000` |
| `PIDPosition_ClosedLoopError` | `7142000` |
| `PIDPosition_Reference` | `7122000` |
| `PIDPosition_ReferenceSlope` | `7232000` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e2000` |
| `PIDTorqueCurrent_FeedForward` | `7062000` |
| `PIDTorqueCurrent_IntegratedAccum` | `7032000` |
| `PIDTorqueCurrent_Output` | `7212000` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b2000` |
| `PIDVelocity_ClosedLoopError` | `7152000` |
| `PIDVelocity_Reference` | `7132000` |
| `PIDVelocity_ReferenceSlope` | `7242000` |
| `Position` | `6fe2000` |
| `ProcessorTemp` | `6f72000` |
| `ReverseLimit` | `6ee2000` |
| `RobotEnable` | `70f2000` |
| `RotorPosition` | `6fa2000` |
| `RotorVelocity` | `6f92000` |
| `StatorCurrent` | `6f32000` |
| `StickyFaultField` | `34d2000` |
| `StickyFault_BootDuringEnable` | `271e2000` |
| `StickyFault_BridgeBrownout` | `27422000` |
| `StickyFault_DeviceTemp` | `27182000` |
| `StickyFault_ForwardHardLimit` | `27572000` |
| `StickyFault_ForwardSoftLimit` | `275d2000` |
| `StickyFault_FusedSensorOutOfSync` | `27692000` |
| `StickyFault_Hardware` | `27122000` |
| `StickyFault_MissingDifferentialFX` | `27482000` |
| `StickyFault_MissingHardLimitRemote` | `27632000` |
| `StickyFault_MissingSoftLimitRemote` | `27602000` |
| `StickyFault_OverSupplyV` | `274e2000` |
| `StickyFault_ProcTemp` | `27152000` |
| `StickyFault_RemoteSensorDataInvalid` | `27662000` |
| `StickyFault_RemoteSensorPosOverflow` | `274b2000` |
| `StickyFault_RemoteSensorReset` | `27452000` |
| `StickyFault_ReverseHardLimit` | `27542000` |
| `StickyFault_ReverseSoftLimit` | `275a2000` |
| `StickyFault_RotorFault1` | `27a22000` |
| `StickyFault_RotorFault2` | `27a52000` |
| `StickyFault_StaticBrakeDisabled` | `27752000` |
| `StickyFault_StatorCurrLimit` | `276c2000` |
| `StickyFault_SupplyCurrLimit` | `276f2000` |
| `StickyFault_Undervoltage` | `271b2000` |
| `StickyFault_UnlicensedFeatureInUse` | `27212000` |
| `StickyFault_UnstableSupplyV` | `27512000` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27722000` |
| `SupplyCurrent` | `6f42000` |
| `SupplyVoltage` | `6f52000` |
| `TorqueCurrent` | `6f22000` |
| `Velocity` | `6fd2000` |
| `Version` | `2e22000` |
| `VersionBugfix` | `2e02000` |
| `VersionBuild` | `2e12000` |
| `VersionMajor` | `2de2000` |
| `VersionMinor` | `2df2000` |

#### `TalonFX-33`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff2100` |
| `AncillaryDeviceTemp` | `82b2100` |
| `AppliedRotorPolarity` | `6ef2100` |
| `BridgeOutput` | `7ab2100` |
| `ClosedLoopSlot` | `7222100` |
| `ConnectedMotor` | `8452100` |
| `ControlMode` | `7072100` |
| `DeviceEnable` | `7102100` |
| `DeviceTemp` | `6f62100` |
| `DutyCycle` | `6f02100` |
| `FaultField` | `34c2100` |
| `Fault_BootDuringEnable` | `271d2100` |
| `Fault_BridgeBrownout` | `27412100` |
| `Fault_DeviceTemp` | `27172100` |
| `Fault_ForwardHardLimit` | `27562100` |
| `Fault_ForwardSoftLimit` | `275c2100` |
| `Fault_FusedSensorOutOfSync` | `27682100` |
| `Fault_Hardware` | `27112100` |
| `Fault_MissingDifferentialFX` | `27472100` |
| `Fault_MissingHardLimitRemote` | `27622100` |
| `Fault_MissingSoftLimitRemote` | `275f2100` |
| `Fault_OverSupplyV` | `274d2100` |
| `Fault_ProcTemp` | `27142100` |
| `Fault_RemoteSensorDataInvalid` | `27652100` |
| `Fault_RemoteSensorPosOverflow` | `274a2100` |
| `Fault_RemoteSensorReset` | `27442100` |
| `Fault_ReverseHardLimit` | `27532100` |
| `Fault_ReverseSoftLimit` | `27592100` |
| `Fault_RotorFault1` | `27a12100` |
| `Fault_RotorFault2` | `27a42100` |
| `Fault_StaticBrakeDisabled` | `27742100` |
| `Fault_StatorCurrLimit` | `276b2100` |
| `Fault_SupplyCurrLimit` | `276e2100` |
| `Fault_Undervoltage` | `271a2100` |
| `Fault_UnlicensedFeatureInUse` | `27202100` |
| `Fault_UnstableSupplyV` | `27502100` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27712100` |
| `ForwardLimit` | `6ed2100` |
| `IsProLicensed` | `8042100` |
| `MotionMagicAtTarget` | `70d2100` |
| `MotionMagicIsRunning` | `70e2100` |
| `MotorKT` | `7522100` |
| `MotorKV` | `7532100` |
| `MotorOutputStatus` | `7262100` |
| `MotorStallCurrent` | `7542100` |
| `MotorVoltage` | `6ec2100` |
| `PIDDutyCycle_DerivativeOutput` | `71c2100` |
| `PIDDutyCycle_FeedForward` | `7042100` |
| `PIDDutyCycle_IntegratedAccum` | `7012100` |
| `PIDDutyCycle_Output` | `71f2100` |
| `PIDDutyCycle_ProportionalOutput` | `7192100` |
| `PIDMotorVoltage_DerivativeOutput` | `71d2100` |
| `PIDMotorVoltage_FeedForward` | `7052100` |
| `PIDMotorVoltage_IntegratedAccum` | `7022100` |
| `PIDMotorVoltage_Output` | `7202100` |
| `PIDMotorVoltage_ProportionalOutput` | `71a2100` |
| `PIDPosition_ClosedLoopError` | `7142100` |
| `PIDPosition_Reference` | `7122100` |
| `PIDPosition_ReferenceSlope` | `7232100` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e2100` |
| `PIDTorqueCurrent_FeedForward` | `7062100` |
| `PIDTorqueCurrent_IntegratedAccum` | `7032100` |
| `PIDTorqueCurrent_Output` | `7212100` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b2100` |
| `PIDVelocity_ClosedLoopError` | `7152100` |
| `PIDVelocity_Reference` | `7132100` |
| `PIDVelocity_ReferenceSlope` | `7242100` |
| `Position` | `6fe2100` |
| `ProcessorTemp` | `6f72100` |
| `ReverseLimit` | `6ee2100` |
| `RobotEnable` | `70f2100` |
| `RotorPosition` | `6fa2100` |
| `RotorVelocity` | `6f92100` |
| `StatorCurrent` | `6f32100` |
| `StickyFaultField` | `34d2100` |
| `StickyFault_BootDuringEnable` | `271e2100` |
| `StickyFault_BridgeBrownout` | `27422100` |
| `StickyFault_DeviceTemp` | `27182100` |
| `StickyFault_ForwardHardLimit` | `27572100` |
| `StickyFault_ForwardSoftLimit` | `275d2100` |
| `StickyFault_FusedSensorOutOfSync` | `27692100` |
| `StickyFault_Hardware` | `27122100` |
| `StickyFault_MissingDifferentialFX` | `27482100` |
| `StickyFault_MissingHardLimitRemote` | `27632100` |
| `StickyFault_MissingSoftLimitRemote` | `27602100` |
| `StickyFault_OverSupplyV` | `274e2100` |
| `StickyFault_ProcTemp` | `27152100` |
| `StickyFault_RemoteSensorDataInvalid` | `27662100` |
| `StickyFault_RemoteSensorPosOverflow` | `274b2100` |
| `StickyFault_RemoteSensorReset` | `27452100` |
| `StickyFault_ReverseHardLimit` | `27542100` |
| `StickyFault_ReverseSoftLimit` | `275a2100` |
| `StickyFault_RotorFault1` | `27a22100` |
| `StickyFault_RotorFault2` | `27a52100` |
| `StickyFault_StaticBrakeDisabled` | `27752100` |
| `StickyFault_StatorCurrLimit` | `276c2100` |
| `StickyFault_SupplyCurrLimit` | `276f2100` |
| `StickyFault_Undervoltage` | `271b2100` |
| `StickyFault_UnlicensedFeatureInUse` | `27212100` |
| `StickyFault_UnstableSupplyV` | `27512100` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27722100` |
| `SupplyCurrent` | `6f42100` |
| `SupplyVoltage` | `6f52100` |
| `TorqueCurrent` | `6f22100` |
| `Velocity` | `6fd2100` |
| `Version` | `2e22100` |
| `VersionBugfix` | `2e02100` |
| `VersionBuild` | `2e12100` |
| `VersionMajor` | `2de2100` |
| `VersionMinor` | `2df2100` |

#### `TalonFX-4`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0400` |
| `AncillaryDeviceTemp` | `82b0400` |
| `AppliedRotorPolarity` | `6ef0400` |
| `BridgeOutput` | `7ab0400` |
| `ClosedLoopSlot` | `7220400` |
| `ConnectedMotor` | `8450400` |
| `ControlMode` | `7070400` |
| `DeviceEnable` | `7100400` |
| `DeviceTemp` | `6f60400` |
| `DutyCycle` | `6f00400` |
| `FaultField` | `34c0400` |
| `Fault_BootDuringEnable` | `271d0400` |
| `Fault_BridgeBrownout` | `27410400` |
| `Fault_DeviceTemp` | `27170400` |
| `Fault_ForwardHardLimit` | `27560400` |
| `Fault_ForwardSoftLimit` | `275c0400` |
| `Fault_FusedSensorOutOfSync` | `27680400` |
| `Fault_Hardware` | `27110400` |
| `Fault_MissingDifferentialFX` | `27470400` |
| `Fault_MissingHardLimitRemote` | `27620400` |
| `Fault_MissingSoftLimitRemote` | `275f0400` |
| `Fault_OverSupplyV` | `274d0400` |
| `Fault_ProcTemp` | `27140400` |
| `Fault_RemoteSensorDataInvalid` | `27650400` |
| `Fault_RemoteSensorPosOverflow` | `274a0400` |
| `Fault_RemoteSensorReset` | `27440400` |
| `Fault_ReverseHardLimit` | `27530400` |
| `Fault_ReverseSoftLimit` | `27590400` |
| `Fault_RotorFault1` | `27a10400` |
| `Fault_RotorFault2` | `27a40400` |
| `Fault_StaticBrakeDisabled` | `27740400` |
| `Fault_StatorCurrLimit` | `276b0400` |
| `Fault_SupplyCurrLimit` | `276e0400` |
| `Fault_Undervoltage` | `271a0400` |
| `Fault_UnlicensedFeatureInUse` | `27200400` |
| `Fault_UnstableSupplyV` | `27500400` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710400` |
| `ForwardLimit` | `6ed0400` |
| `IsProLicensed` | `8040400` |
| `MotionMagicAtTarget` | `70d0400` |
| `MotionMagicIsRunning` | `70e0400` |
| `MotorKT` | `7520400` |
| `MotorKV` | `7530400` |
| `MotorOutputStatus` | `7260400` |
| `MotorStallCurrent` | `7540400` |
| `MotorVoltage` | `6ec0400` |
| `PIDDutyCycle_DerivativeOutput` | `71c0400` |
| `PIDDutyCycle_FeedForward` | `7040400` |
| `PIDDutyCycle_IntegratedAccum` | `7010400` |
| `PIDDutyCycle_Output` | `71f0400` |
| `PIDDutyCycle_ProportionalOutput` | `7190400` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0400` |
| `PIDMotorVoltage_FeedForward` | `7050400` |
| `PIDMotorVoltage_IntegratedAccum` | `7020400` |
| `PIDMotorVoltage_Output` | `7200400` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0400` |
| `PIDPosition_ClosedLoopError` | `7140400` |
| `PIDPosition_Reference` | `7120400` |
| `PIDPosition_ReferenceSlope` | `7230400` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0400` |
| `PIDTorqueCurrent_FeedForward` | `7060400` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030400` |
| `PIDTorqueCurrent_Output` | `7210400` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0400` |
| `PIDVelocity_ClosedLoopError` | `7150400` |
| `PIDVelocity_Reference` | `7130400` |
| `PIDVelocity_ReferenceSlope` | `7240400` |
| `Position` | `6fe0400` |
| `ProcessorTemp` | `6f70400` |
| `ReverseLimit` | `6ee0400` |
| `RobotEnable` | `70f0400` |
| `RotorPosition` | `6fa0400` |
| `RotorVelocity` | `6f90400` |
| `StatorCurrent` | `6f30400` |
| `StickyFaultField` | `34d0400` |
| `StickyFault_BootDuringEnable` | `271e0400` |
| `StickyFault_BridgeBrownout` | `27420400` |
| `StickyFault_DeviceTemp` | `27180400` |
| `StickyFault_ForwardHardLimit` | `27570400` |
| `StickyFault_ForwardSoftLimit` | `275d0400` |
| `StickyFault_FusedSensorOutOfSync` | `27690400` |
| `StickyFault_Hardware` | `27120400` |
| `StickyFault_MissingDifferentialFX` | `27480400` |
| `StickyFault_MissingHardLimitRemote` | `27630400` |
| `StickyFault_MissingSoftLimitRemote` | `27600400` |
| `StickyFault_OverSupplyV` | `274e0400` |
| `StickyFault_ProcTemp` | `27150400` |
| `StickyFault_RemoteSensorDataInvalid` | `27660400` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0400` |
| `StickyFault_RemoteSensorReset` | `27450400` |
| `StickyFault_ReverseHardLimit` | `27540400` |
| `StickyFault_ReverseSoftLimit` | `275a0400` |
| `StickyFault_RotorFault1` | `27a20400` |
| `StickyFault_RotorFault2` | `27a50400` |
| `StickyFault_StaticBrakeDisabled` | `27750400` |
| `StickyFault_StatorCurrLimit` | `276c0400` |
| `StickyFault_SupplyCurrLimit` | `276f0400` |
| `StickyFault_Undervoltage` | `271b0400` |
| `StickyFault_UnlicensedFeatureInUse` | `27210400` |
| `StickyFault_UnstableSupplyV` | `27510400` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720400` |
| `SupplyCurrent` | `6f40400` |
| `SupplyVoltage` | `6f50400` |
| `TorqueCurrent` | `6f20400` |
| `Velocity` | `6fd0400` |
| `Version` | `2e20400` |
| `VersionBugfix` | `2e00400` |
| `VersionBuild` | `2e10400` |
| `VersionMajor` | `2de0400` |
| `VersionMinor` | `2df0400` |

#### `TalonFX-5`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0500` |
| `AncillaryDeviceTemp` | `82b0500` |
| `AppliedRotorPolarity` | `6ef0500` |
| `BridgeOutput` | `7ab0500` |
| `ClosedLoopSlot` | `7220500` |
| `ConnectedMotor` | `8450500` |
| `ControlMode` | `7070500` |
| `DeviceEnable` | `7100500` |
| `DeviceTemp` | `6f60500` |
| `DutyCycle` | `6f00500` |
| `FaultField` | `34c0500` |
| `Fault_BootDuringEnable` | `271d0500` |
| `Fault_BridgeBrownout` | `27410500` |
| `Fault_DeviceTemp` | `27170500` |
| `Fault_ForwardHardLimit` | `27560500` |
| `Fault_ForwardSoftLimit` | `275c0500` |
| `Fault_FusedSensorOutOfSync` | `27680500` |
| `Fault_Hardware` | `27110500` |
| `Fault_MissingDifferentialFX` | `27470500` |
| `Fault_MissingHardLimitRemote` | `27620500` |
| `Fault_MissingSoftLimitRemote` | `275f0500` |
| `Fault_OverSupplyV` | `274d0500` |
| `Fault_ProcTemp` | `27140500` |
| `Fault_RemoteSensorDataInvalid` | `27650500` |
| `Fault_RemoteSensorPosOverflow` | `274a0500` |
| `Fault_RemoteSensorReset` | `27440500` |
| `Fault_ReverseHardLimit` | `27530500` |
| `Fault_ReverseSoftLimit` | `27590500` |
| `Fault_RotorFault1` | `27a10500` |
| `Fault_RotorFault2` | `27a40500` |
| `Fault_StaticBrakeDisabled` | `27740500` |
| `Fault_StatorCurrLimit` | `276b0500` |
| `Fault_SupplyCurrLimit` | `276e0500` |
| `Fault_Undervoltage` | `271a0500` |
| `Fault_UnlicensedFeatureInUse` | `27200500` |
| `Fault_UnstableSupplyV` | `27500500` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710500` |
| `ForwardLimit` | `6ed0500` |
| `IsProLicensed` | `8040500` |
| `MotionMagicAtTarget` | `70d0500` |
| `MotionMagicIsRunning` | `70e0500` |
| `MotorKT` | `7520500` |
| `MotorKV` | `7530500` |
| `MotorOutputStatus` | `7260500` |
| `MotorStallCurrent` | `7540500` |
| `MotorVoltage` | `6ec0500` |
| `PIDDutyCycle_DerivativeOutput` | `71c0500` |
| `PIDDutyCycle_FeedForward` | `7040500` |
| `PIDDutyCycle_IntegratedAccum` | `7010500` |
| `PIDDutyCycle_Output` | `71f0500` |
| `PIDDutyCycle_ProportionalOutput` | `7190500` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0500` |
| `PIDMotorVoltage_FeedForward` | `7050500` |
| `PIDMotorVoltage_IntegratedAccum` | `7020500` |
| `PIDMotorVoltage_Output` | `7200500` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0500` |
| `PIDPosition_ClosedLoopError` | `7140500` |
| `PIDPosition_Reference` | `7120500` |
| `PIDPosition_ReferenceSlope` | `7230500` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0500` |
| `PIDTorqueCurrent_FeedForward` | `7060500` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030500` |
| `PIDTorqueCurrent_Output` | `7210500` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0500` |
| `PIDVelocity_ClosedLoopError` | `7150500` |
| `PIDVelocity_Reference` | `7130500` |
| `PIDVelocity_ReferenceSlope` | `7240500` |
| `Position` | `6fe0500` |
| `ProcessorTemp` | `6f70500` |
| `ReverseLimit` | `6ee0500` |
| `RobotEnable` | `70f0500` |
| `RotorPosition` | `6fa0500` |
| `RotorVelocity` | `6f90500` |
| `StatorCurrent` | `6f30500` |
| `StickyFaultField` | `34d0500` |
| `StickyFault_BootDuringEnable` | `271e0500` |
| `StickyFault_BridgeBrownout` | `27420500` |
| `StickyFault_DeviceTemp` | `27180500` |
| `StickyFault_ForwardHardLimit` | `27570500` |
| `StickyFault_ForwardSoftLimit` | `275d0500` |
| `StickyFault_FusedSensorOutOfSync` | `27690500` |
| `StickyFault_Hardware` | `27120500` |
| `StickyFault_MissingDifferentialFX` | `27480500` |
| `StickyFault_MissingHardLimitRemote` | `27630500` |
| `StickyFault_MissingSoftLimitRemote` | `27600500` |
| `StickyFault_OverSupplyV` | `274e0500` |
| `StickyFault_ProcTemp` | `27150500` |
| `StickyFault_RemoteSensorDataInvalid` | `27660500` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0500` |
| `StickyFault_RemoteSensorReset` | `27450500` |
| `StickyFault_ReverseHardLimit` | `27540500` |
| `StickyFault_ReverseSoftLimit` | `275a0500` |
| `StickyFault_RotorFault1` | `27a20500` |
| `StickyFault_RotorFault2` | `27a50500` |
| `StickyFault_StaticBrakeDisabled` | `27750500` |
| `StickyFault_StatorCurrLimit` | `276c0500` |
| `StickyFault_SupplyCurrLimit` | `276f0500` |
| `StickyFault_Undervoltage` | `271b0500` |
| `StickyFault_UnlicensedFeatureInUse` | `27210500` |
| `StickyFault_UnstableSupplyV` | `27510500` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720500` |
| `SupplyCurrent` | `6f40500` |
| `SupplyVoltage` | `6f50500` |
| `TorqueCurrent` | `6f20500` |
| `Velocity` | `6fd0500` |
| `Version` | `2e20500` |
| `VersionBugfix` | `2e00500` |
| `VersionBuild` | `2e10500` |
| `VersionMajor` | `2de0500` |
| `VersionMinor` | `2df0500` |

#### `TalonFX-51`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff3300` |
| `AncillaryDeviceTemp` | `82b3300` |
| `AppliedRotorPolarity` | `6ef3300` |
| `BridgeOutput` | `7ab3300` |
| `ClosedLoopSlot` | `7223300` |
| `ConnectedMotor` | `8453300` |
| `ControlMode` | `7073300` |
| `DeviceEnable` | `7103300` |
| `DeviceTemp` | `6f63300` |
| `DutyCycle` | `6f03300` |
| `FaultField` | `34c3300` |
| `Fault_BootDuringEnable` | `271d3300` |
| `Fault_BridgeBrownout` | `27413300` |
| `Fault_DeviceTemp` | `27173300` |
| `Fault_ForwardHardLimit` | `27563300` |
| `Fault_ForwardSoftLimit` | `275c3300` |
| `Fault_FusedSensorOutOfSync` | `27683300` |
| `Fault_Hardware` | `27113300` |
| `Fault_MissingDifferentialFX` | `27473300` |
| `Fault_MissingHardLimitRemote` | `27623300` |
| `Fault_MissingSoftLimitRemote` | `275f3300` |
| `Fault_OverSupplyV` | `274d3300` |
| `Fault_ProcTemp` | `27143300` |
| `Fault_RemoteSensorDataInvalid` | `27653300` |
| `Fault_RemoteSensorPosOverflow` | `274a3300` |
| `Fault_RemoteSensorReset` | `27443300` |
| `Fault_ReverseHardLimit` | `27533300` |
| `Fault_ReverseSoftLimit` | `27593300` |
| `Fault_RotorFault1` | `27a13300` |
| `Fault_RotorFault2` | `27a43300` |
| `Fault_StaticBrakeDisabled` | `27743300` |
| `Fault_StatorCurrLimit` | `276b3300` |
| `Fault_SupplyCurrLimit` | `276e3300` |
| `Fault_Undervoltage` | `271a3300` |
| `Fault_UnlicensedFeatureInUse` | `27203300` |
| `Fault_UnstableSupplyV` | `27503300` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27713300` |
| `ForwardLimit` | `6ed3300` |
| `IsProLicensed` | `8043300` |
| `MotionMagicAtTarget` | `70d3300` |
| `MotionMagicIsRunning` | `70e3300` |
| `MotorKT` | `7523300` |
| `MotorKV` | `7533300` |
| `MotorOutputStatus` | `7263300` |
| `MotorStallCurrent` | `7543300` |
| `MotorVoltage` | `6ec3300` |
| `PIDDutyCycle_DerivativeOutput` | `71c3300` |
| `PIDDutyCycle_FeedForward` | `7043300` |
| `PIDDutyCycle_IntegratedAccum` | `7013300` |
| `PIDDutyCycle_Output` | `71f3300` |
| `PIDDutyCycle_ProportionalOutput` | `7193300` |
| `PIDMotorVoltage_DerivativeOutput` | `71d3300` |
| `PIDMotorVoltage_FeedForward` | `7053300` |
| `PIDMotorVoltage_IntegratedAccum` | `7023300` |
| `PIDMotorVoltage_Output` | `7203300` |
| `PIDMotorVoltage_ProportionalOutput` | `71a3300` |
| `PIDPosition_ClosedLoopError` | `7143300` |
| `PIDPosition_Reference` | `7123300` |
| `PIDPosition_ReferenceSlope` | `7233300` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e3300` |
| `PIDTorqueCurrent_FeedForward` | `7063300` |
| `PIDTorqueCurrent_IntegratedAccum` | `7033300` |
| `PIDTorqueCurrent_Output` | `7213300` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b3300` |
| `PIDVelocity_ClosedLoopError` | `7153300` |
| `PIDVelocity_Reference` | `7133300` |
| `PIDVelocity_ReferenceSlope` | `7243300` |
| `Position` | `6fe3300` |
| `ProcessorTemp` | `6f73300` |
| `ReverseLimit` | `6ee3300` |
| `RobotEnable` | `70f3300` |
| `RotorPosition` | `6fa3300` |
| `RotorVelocity` | `6f93300` |
| `StatorCurrent` | `6f33300` |
| `StickyFaultField` | `34d3300` |
| `StickyFault_BootDuringEnable` | `271e3300` |
| `StickyFault_BridgeBrownout` | `27423300` |
| `StickyFault_DeviceTemp` | `27183300` |
| `StickyFault_ForwardHardLimit` | `27573300` |
| `StickyFault_ForwardSoftLimit` | `275d3300` |
| `StickyFault_FusedSensorOutOfSync` | `27693300` |
| `StickyFault_Hardware` | `27123300` |
| `StickyFault_MissingDifferentialFX` | `27483300` |
| `StickyFault_MissingHardLimitRemote` | `27633300` |
| `StickyFault_MissingSoftLimitRemote` | `27603300` |
| `StickyFault_OverSupplyV` | `274e3300` |
| `StickyFault_ProcTemp` | `27153300` |
| `StickyFault_RemoteSensorDataInvalid` | `27663300` |
| `StickyFault_RemoteSensorPosOverflow` | `274b3300` |
| `StickyFault_RemoteSensorReset` | `27453300` |
| `StickyFault_ReverseHardLimit` | `27543300` |
| `StickyFault_ReverseSoftLimit` | `275a3300` |
| `StickyFault_RotorFault1` | `27a23300` |
| `StickyFault_RotorFault2` | `27a53300` |
| `StickyFault_StaticBrakeDisabled` | `27753300` |
| `StickyFault_StatorCurrLimit` | `276c3300` |
| `StickyFault_SupplyCurrLimit` | `276f3300` |
| `StickyFault_Undervoltage` | `271b3300` |
| `StickyFault_UnlicensedFeatureInUse` | `27213300` |
| `StickyFault_UnstableSupplyV` | `27513300` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27723300` |
| `SupplyCurrent` | `6f43300` |
| `SupplyVoltage` | `6f53300` |
| `TorqueCurrent` | `6f23300` |
| `Velocity` | `6fd3300` |
| `Version` | `2e23300` |
| `VersionBugfix` | `2e03300` |
| `VersionBuild` | `2e13300` |
| `VersionMajor` | `2de3300` |
| `VersionMinor` | `2df3300` |

#### `TalonFX-52`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff3400` |
| `AncillaryDeviceTemp` | `82b3400` |
| `AppliedRotorPolarity` | `6ef3400` |
| `BridgeOutput` | `7ab3400` |
| `ClosedLoopSlot` | `7223400` |
| `ConnectedMotor` | `8453400` |
| `ControlMode` | `7073400` |
| `DeviceEnable` | `7103400` |
| `DeviceTemp` | `6f63400` |
| `DutyCycle` | `6f03400` |
| `FaultField` | `34c3400` |
| `Fault_BootDuringEnable` | `271d3400` |
| `Fault_BridgeBrownout` | `27413400` |
| `Fault_DeviceTemp` | `27173400` |
| `Fault_ForwardHardLimit` | `27563400` |
| `Fault_ForwardSoftLimit` | `275c3400` |
| `Fault_FusedSensorOutOfSync` | `27683400` |
| `Fault_Hardware` | `27113400` |
| `Fault_MissingDifferentialFX` | `27473400` |
| `Fault_MissingHardLimitRemote` | `27623400` |
| `Fault_MissingSoftLimitRemote` | `275f3400` |
| `Fault_OverSupplyV` | `274d3400` |
| `Fault_ProcTemp` | `27143400` |
| `Fault_RemoteSensorDataInvalid` | `27653400` |
| `Fault_RemoteSensorPosOverflow` | `274a3400` |
| `Fault_RemoteSensorReset` | `27443400` |
| `Fault_ReverseHardLimit` | `27533400` |
| `Fault_ReverseSoftLimit` | `27593400` |
| `Fault_RotorFault1` | `27a13400` |
| `Fault_RotorFault2` | `27a43400` |
| `Fault_StaticBrakeDisabled` | `27743400` |
| `Fault_StatorCurrLimit` | `276b3400` |
| `Fault_SupplyCurrLimit` | `276e3400` |
| `Fault_Undervoltage` | `271a3400` |
| `Fault_UnlicensedFeatureInUse` | `27203400` |
| `Fault_UnstableSupplyV` | `27503400` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27713400` |
| `ForwardLimit` | `6ed3400` |
| `IsProLicensed` | `8043400` |
| `MotionMagicAtTarget` | `70d3400` |
| `MotionMagicIsRunning` | `70e3400` |
| `MotorKT` | `7523400` |
| `MotorKV` | `7533400` |
| `MotorOutputStatus` | `7263400` |
| `MotorStallCurrent` | `7543400` |
| `MotorVoltage` | `6ec3400` |
| `PIDDutyCycle_DerivativeOutput` | `71c3400` |
| `PIDDutyCycle_FeedForward` | `7043400` |
| `PIDDutyCycle_IntegratedAccum` | `7013400` |
| `PIDDutyCycle_Output` | `71f3400` |
| `PIDDutyCycle_ProportionalOutput` | `7193400` |
| `PIDMotorVoltage_DerivativeOutput` | `71d3400` |
| `PIDMotorVoltage_FeedForward` | `7053400` |
| `PIDMotorVoltage_IntegratedAccum` | `7023400` |
| `PIDMotorVoltage_Output` | `7203400` |
| `PIDMotorVoltage_ProportionalOutput` | `71a3400` |
| `PIDPosition_ClosedLoopError` | `7143400` |
| `PIDPosition_Reference` | `7123400` |
| `PIDPosition_ReferenceSlope` | `7233400` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e3400` |
| `PIDTorqueCurrent_FeedForward` | `7063400` |
| `PIDTorqueCurrent_IntegratedAccum` | `7033400` |
| `PIDTorqueCurrent_Output` | `7213400` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b3400` |
| `PIDVelocity_ClosedLoopError` | `7153400` |
| `PIDVelocity_Reference` | `7133400` |
| `PIDVelocity_ReferenceSlope` | `7243400` |
| `Position` | `6fe3400` |
| `ProcessorTemp` | `6f73400` |
| `ReverseLimit` | `6ee3400` |
| `RobotEnable` | `70f3400` |
| `RotorPosition` | `6fa3400` |
| `RotorVelocity` | `6f93400` |
| `StatorCurrent` | `6f33400` |
| `StickyFaultField` | `34d3400` |
| `StickyFault_BootDuringEnable` | `271e3400` |
| `StickyFault_BridgeBrownout` | `27423400` |
| `StickyFault_DeviceTemp` | `27183400` |
| `StickyFault_ForwardHardLimit` | `27573400` |
| `StickyFault_ForwardSoftLimit` | `275d3400` |
| `StickyFault_FusedSensorOutOfSync` | `27693400` |
| `StickyFault_Hardware` | `27123400` |
| `StickyFault_MissingDifferentialFX` | `27483400` |
| `StickyFault_MissingHardLimitRemote` | `27633400` |
| `StickyFault_MissingSoftLimitRemote` | `27603400` |
| `StickyFault_OverSupplyV` | `274e3400` |
| `StickyFault_ProcTemp` | `27153400` |
| `StickyFault_RemoteSensorDataInvalid` | `27663400` |
| `StickyFault_RemoteSensorPosOverflow` | `274b3400` |
| `StickyFault_RemoteSensorReset` | `27453400` |
| `StickyFault_ReverseHardLimit` | `27543400` |
| `StickyFault_ReverseSoftLimit` | `275a3400` |
| `StickyFault_RotorFault1` | `27a23400` |
| `StickyFault_RotorFault2` | `27a53400` |
| `StickyFault_StaticBrakeDisabled` | `27753400` |
| `StickyFault_StatorCurrLimit` | `276c3400` |
| `StickyFault_SupplyCurrLimit` | `276f3400` |
| `StickyFault_Undervoltage` | `271b3400` |
| `StickyFault_UnlicensedFeatureInUse` | `27213400` |
| `StickyFault_UnstableSupplyV` | `27513400` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27723400` |
| `SupplyCurrent` | `6f43400` |
| `SupplyVoltage` | `6f53400` |
| `TorqueCurrent` | `6f23400` |
| `Velocity` | `6fd3400` |
| `Version` | `2e23400` |
| `VersionBugfix` | `2e03400` |
| `VersionBuild` | `2e13400` |
| `VersionMajor` | `2de3400` |
| `VersionMinor` | `2df3400` |

#### `TalonFX-6`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0600` |
| `AncillaryDeviceTemp` | `82b0600` |
| `AppliedRotorPolarity` | `6ef0600` |
| `BridgeOutput` | `7ab0600` |
| `ClosedLoopSlot` | `7220600` |
| `ConnectedMotor` | `8450600` |
| `ControlMode` | `7070600` |
| `DeviceEnable` | `7100600` |
| `DeviceTemp` | `6f60600` |
| `DutyCycle` | `6f00600` |
| `FaultField` | `34c0600` |
| `Fault_BootDuringEnable` | `271d0600` |
| `Fault_BridgeBrownout` | `27410600` |
| `Fault_DeviceTemp` | `27170600` |
| `Fault_ForwardHardLimit` | `27560600` |
| `Fault_ForwardSoftLimit` | `275c0600` |
| `Fault_FusedSensorOutOfSync` | `27680600` |
| `Fault_Hardware` | `27110600` |
| `Fault_MissingDifferentialFX` | `27470600` |
| `Fault_MissingHardLimitRemote` | `27620600` |
| `Fault_MissingSoftLimitRemote` | `275f0600` |
| `Fault_OverSupplyV` | `274d0600` |
| `Fault_ProcTemp` | `27140600` |
| `Fault_RemoteSensorDataInvalid` | `27650600` |
| `Fault_RemoteSensorPosOverflow` | `274a0600` |
| `Fault_RemoteSensorReset` | `27440600` |
| `Fault_ReverseHardLimit` | `27530600` |
| `Fault_ReverseSoftLimit` | `27590600` |
| `Fault_RotorFault1` | `27a10600` |
| `Fault_RotorFault2` | `27a40600` |
| `Fault_StaticBrakeDisabled` | `27740600` |
| `Fault_StatorCurrLimit` | `276b0600` |
| `Fault_SupplyCurrLimit` | `276e0600` |
| `Fault_Undervoltage` | `271a0600` |
| `Fault_UnlicensedFeatureInUse` | `27200600` |
| `Fault_UnstableSupplyV` | `27500600` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710600` |
| `ForwardLimit` | `6ed0600` |
| `IsProLicensed` | `8040600` |
| `MotionMagicAtTarget` | `70d0600` |
| `MotionMagicIsRunning` | `70e0600` |
| `MotorKT` | `7520600` |
| `MotorKV` | `7530600` |
| `MotorOutputStatus` | `7260600` |
| `MotorStallCurrent` | `7540600` |
| `MotorVoltage` | `6ec0600` |
| `PIDDutyCycle_DerivativeOutput` | `71c0600` |
| `PIDDutyCycle_FeedForward` | `7040600` |
| `PIDDutyCycle_IntegratedAccum` | `7010600` |
| `PIDDutyCycle_Output` | `71f0600` |
| `PIDDutyCycle_ProportionalOutput` | `7190600` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0600` |
| `PIDMotorVoltage_FeedForward` | `7050600` |
| `PIDMotorVoltage_IntegratedAccum` | `7020600` |
| `PIDMotorVoltage_Output` | `7200600` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0600` |
| `PIDPosition_ClosedLoopError` | `7140600` |
| `PIDPosition_Reference` | `7120600` |
| `PIDPosition_ReferenceSlope` | `7230600` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0600` |
| `PIDTorqueCurrent_FeedForward` | `7060600` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030600` |
| `PIDTorqueCurrent_Output` | `7210600` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0600` |
| `PIDVelocity_ClosedLoopError` | `7150600` |
| `PIDVelocity_Reference` | `7130600` |
| `PIDVelocity_ReferenceSlope` | `7240600` |
| `Position` | `6fe0600` |
| `ProcessorTemp` | `6f70600` |
| `ReverseLimit` | `6ee0600` |
| `RobotEnable` | `70f0600` |
| `RotorPosition` | `6fa0600` |
| `RotorVelocity` | `6f90600` |
| `StatorCurrent` | `6f30600` |
| `StickyFaultField` | `34d0600` |
| `StickyFault_BootDuringEnable` | `271e0600` |
| `StickyFault_BridgeBrownout` | `27420600` |
| `StickyFault_DeviceTemp` | `27180600` |
| `StickyFault_ForwardHardLimit` | `27570600` |
| `StickyFault_ForwardSoftLimit` | `275d0600` |
| `StickyFault_FusedSensorOutOfSync` | `27690600` |
| `StickyFault_Hardware` | `27120600` |
| `StickyFault_MissingDifferentialFX` | `27480600` |
| `StickyFault_MissingHardLimitRemote` | `27630600` |
| `StickyFault_MissingSoftLimitRemote` | `27600600` |
| `StickyFault_OverSupplyV` | `274e0600` |
| `StickyFault_ProcTemp` | `27150600` |
| `StickyFault_RemoteSensorDataInvalid` | `27660600` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0600` |
| `StickyFault_RemoteSensorReset` | `27450600` |
| `StickyFault_ReverseHardLimit` | `27540600` |
| `StickyFault_ReverseSoftLimit` | `275a0600` |
| `StickyFault_RotorFault1` | `27a20600` |
| `StickyFault_RotorFault2` | `27a50600` |
| `StickyFault_StaticBrakeDisabled` | `27750600` |
| `StickyFault_StatorCurrLimit` | `276c0600` |
| `StickyFault_SupplyCurrLimit` | `276f0600` |
| `StickyFault_Undervoltage` | `271b0600` |
| `StickyFault_UnlicensedFeatureInUse` | `27210600` |
| `StickyFault_UnstableSupplyV` | `27510600` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720600` |
| `SupplyCurrent` | `6f40600` |
| `SupplyVoltage` | `6f50600` |
| `TorqueCurrent` | `6f20600` |
| `Velocity` | `6fd0600` |
| `Version` | `2e20600` |
| `VersionBugfix` | `2e00600` |
| `VersionBuild` | `2e10600` |
| `VersionMajor` | `2de0600` |
| `VersionMinor` | `2df0600` |

#### `TalonFX-7`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0700` |
| `AncillaryDeviceTemp` | `82b0700` |
| `AppliedRotorPolarity` | `6ef0700` |
| `BridgeOutput` | `7ab0700` |
| `ClosedLoopSlot` | `7220700` |
| `ConnectedMotor` | `8450700` |
| `ControlMode` | `7070700` |
| `DeviceEnable` | `7100700` |
| `DeviceTemp` | `6f60700` |
| `DutyCycle` | `6f00700` |
| `FaultField` | `34c0700` |
| `Fault_BootDuringEnable` | `271d0700` |
| `Fault_BridgeBrownout` | `27410700` |
| `Fault_DeviceTemp` | `27170700` |
| `Fault_ForwardHardLimit` | `27560700` |
| `Fault_ForwardSoftLimit` | `275c0700` |
| `Fault_FusedSensorOutOfSync` | `27680700` |
| `Fault_Hardware` | `27110700` |
| `Fault_MissingDifferentialFX` | `27470700` |
| `Fault_MissingHardLimitRemote` | `27620700` |
| `Fault_MissingSoftLimitRemote` | `275f0700` |
| `Fault_OverSupplyV` | `274d0700` |
| `Fault_ProcTemp` | `27140700` |
| `Fault_RemoteSensorDataInvalid` | `27650700` |
| `Fault_RemoteSensorPosOverflow` | `274a0700` |
| `Fault_RemoteSensorReset` | `27440700` |
| `Fault_ReverseHardLimit` | `27530700` |
| `Fault_ReverseSoftLimit` | `27590700` |
| `Fault_RotorFault1` | `27a10700` |
| `Fault_RotorFault2` | `27a40700` |
| `Fault_StaticBrakeDisabled` | `27740700` |
| `Fault_StatorCurrLimit` | `276b0700` |
| `Fault_SupplyCurrLimit` | `276e0700` |
| `Fault_Undervoltage` | `271a0700` |
| `Fault_UnlicensedFeatureInUse` | `27200700` |
| `Fault_UnstableSupplyV` | `27500700` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710700` |
| `ForwardLimit` | `6ed0700` |
| `IsProLicensed` | `8040700` |
| `MotionMagicAtTarget` | `70d0700` |
| `MotionMagicIsRunning` | `70e0700` |
| `MotorKT` | `7520700` |
| `MotorKV` | `7530700` |
| `MotorOutputStatus` | `7260700` |
| `MotorStallCurrent` | `7540700` |
| `MotorVoltage` | `6ec0700` |
| `PIDDutyCycle_DerivativeOutput` | `71c0700` |
| `PIDDutyCycle_FeedForward` | `7040700` |
| `PIDDutyCycle_IntegratedAccum` | `7010700` |
| `PIDDutyCycle_Output` | `71f0700` |
| `PIDDutyCycle_ProportionalOutput` | `7190700` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0700` |
| `PIDMotorVoltage_FeedForward` | `7050700` |
| `PIDMotorVoltage_IntegratedAccum` | `7020700` |
| `PIDMotorVoltage_Output` | `7200700` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0700` |
| `PIDPosition_ClosedLoopError` | `7140700` |
| `PIDPosition_Reference` | `7120700` |
| `PIDPosition_ReferenceSlope` | `7230700` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0700` |
| `PIDTorqueCurrent_FeedForward` | `7060700` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030700` |
| `PIDTorqueCurrent_Output` | `7210700` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0700` |
| `PIDVelocity_ClosedLoopError` | `7150700` |
| `PIDVelocity_Reference` | `7130700` |
| `PIDVelocity_ReferenceSlope` | `7240700` |
| `Position` | `6fe0700` |
| `ProcessorTemp` | `6f70700` |
| `ReverseLimit` | `6ee0700` |
| `RobotEnable` | `70f0700` |
| `RotorPosition` | `6fa0700` |
| `RotorVelocity` | `6f90700` |
| `StatorCurrent` | `6f30700` |
| `StickyFaultField` | `34d0700` |
| `StickyFault_BootDuringEnable` | `271e0700` |
| `StickyFault_BridgeBrownout` | `27420700` |
| `StickyFault_DeviceTemp` | `27180700` |
| `StickyFault_ForwardHardLimit` | `27570700` |
| `StickyFault_ForwardSoftLimit` | `275d0700` |
| `StickyFault_FusedSensorOutOfSync` | `27690700` |
| `StickyFault_Hardware` | `27120700` |
| `StickyFault_MissingDifferentialFX` | `27480700` |
| `StickyFault_MissingHardLimitRemote` | `27630700` |
| `StickyFault_MissingSoftLimitRemote` | `27600700` |
| `StickyFault_OverSupplyV` | `274e0700` |
| `StickyFault_ProcTemp` | `27150700` |
| `StickyFault_RemoteSensorDataInvalid` | `27660700` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0700` |
| `StickyFault_RemoteSensorReset` | `27450700` |
| `StickyFault_ReverseHardLimit` | `27540700` |
| `StickyFault_ReverseSoftLimit` | `275a0700` |
| `StickyFault_RotorFault1` | `27a20700` |
| `StickyFault_RotorFault2` | `27a50700` |
| `StickyFault_StaticBrakeDisabled` | `27750700` |
| `StickyFault_StatorCurrLimit` | `276c0700` |
| `StickyFault_SupplyCurrLimit` | `276f0700` |
| `StickyFault_Undervoltage` | `271b0700` |
| `StickyFault_UnlicensedFeatureInUse` | `27210700` |
| `StickyFault_UnstableSupplyV` | `27510700` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720700` |
| `SupplyCurrent` | `6f40700` |
| `SupplyVoltage` | `6f50700` |
| `TorqueCurrent` | `6f20700` |
| `Velocity` | `6fd0700` |
| `Version` | `2e20700` |
| `VersionBugfix` | `2e00700` |
| `VersionBuild` | `2e10700` |
| `VersionMajor` | `2de0700` |
| `VersionMinor` | `2df0700` |

#### `TalonFX-8`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0800` |
| `AncillaryDeviceTemp` | `82b0800` |
| `AppliedRotorPolarity` | `6ef0800` |
| `BridgeOutput` | `7ab0800` |
| `ClosedLoopSlot` | `7220800` |
| `ConnectedMotor` | `8450800` |
| `ControlMode` | `7070800` |
| `DeviceEnable` | `7100800` |
| `DeviceTemp` | `6f60800` |
| `DutyCycle` | `6f00800` |
| `FaultField` | `34c0800` |
| `Fault_BootDuringEnable` | `271d0800` |
| `Fault_BridgeBrownout` | `27410800` |
| `Fault_DeviceTemp` | `27170800` |
| `Fault_ForwardHardLimit` | `27560800` |
| `Fault_ForwardSoftLimit` | `275c0800` |
| `Fault_FusedSensorOutOfSync` | `27680800` |
| `Fault_Hardware` | `27110800` |
| `Fault_MissingDifferentialFX` | `27470800` |
| `Fault_MissingHardLimitRemote` | `27620800` |
| `Fault_MissingSoftLimitRemote` | `275f0800` |
| `Fault_OverSupplyV` | `274d0800` |
| `Fault_ProcTemp` | `27140800` |
| `Fault_RemoteSensorDataInvalid` | `27650800` |
| `Fault_RemoteSensorPosOverflow` | `274a0800` |
| `Fault_RemoteSensorReset` | `27440800` |
| `Fault_ReverseHardLimit` | `27530800` |
| `Fault_ReverseSoftLimit` | `27590800` |
| `Fault_RotorFault1` | `27a10800` |
| `Fault_RotorFault2` | `27a40800` |
| `Fault_StaticBrakeDisabled` | `27740800` |
| `Fault_StatorCurrLimit` | `276b0800` |
| `Fault_SupplyCurrLimit` | `276e0800` |
| `Fault_Undervoltage` | `271a0800` |
| `Fault_UnlicensedFeatureInUse` | `27200800` |
| `Fault_UnstableSupplyV` | `27500800` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710800` |
| `ForwardLimit` | `6ed0800` |
| `IsProLicensed` | `8040800` |
| `MotionMagicAtTarget` | `70d0800` |
| `MotionMagicIsRunning` | `70e0800` |
| `MotorKT` | `7520800` |
| `MotorKV` | `7530800` |
| `MotorOutputStatus` | `7260800` |
| `MotorStallCurrent` | `7540800` |
| `MotorVoltage` | `6ec0800` |
| `PIDDutyCycle_DerivativeOutput` | `71c0800` |
| `PIDDutyCycle_FeedForward` | `7040800` |
| `PIDDutyCycle_IntegratedAccum` | `7010800` |
| `PIDDutyCycle_Output` | `71f0800` |
| `PIDDutyCycle_ProportionalOutput` | `7190800` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0800` |
| `PIDMotorVoltage_FeedForward` | `7050800` |
| `PIDMotorVoltage_IntegratedAccum` | `7020800` |
| `PIDMotorVoltage_Output` | `7200800` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0800` |
| `PIDPosition_ClosedLoopError` | `7140800` |
| `PIDPosition_Reference` | `7120800` |
| `PIDPosition_ReferenceSlope` | `7230800` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0800` |
| `PIDTorqueCurrent_FeedForward` | `7060800` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030800` |
| `PIDTorqueCurrent_Output` | `7210800` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0800` |
| `PIDVelocity_ClosedLoopError` | `7150800` |
| `PIDVelocity_Reference` | `7130800` |
| `PIDVelocity_ReferenceSlope` | `7240800` |
| `Position` | `6fe0800` |
| `ProcessorTemp` | `6f70800` |
| `ReverseLimit` | `6ee0800` |
| `RobotEnable` | `70f0800` |
| `RotorPosition` | `6fa0800` |
| `RotorVelocity` | `6f90800` |
| `StatorCurrent` | `6f30800` |
| `StickyFaultField` | `34d0800` |
| `StickyFault_BootDuringEnable` | `271e0800` |
| `StickyFault_BridgeBrownout` | `27420800` |
| `StickyFault_DeviceTemp` | `27180800` |
| `StickyFault_ForwardHardLimit` | `27570800` |
| `StickyFault_ForwardSoftLimit` | `275d0800` |
| `StickyFault_FusedSensorOutOfSync` | `27690800` |
| `StickyFault_Hardware` | `27120800` |
| `StickyFault_MissingDifferentialFX` | `27480800` |
| `StickyFault_MissingHardLimitRemote` | `27630800` |
| `StickyFault_MissingSoftLimitRemote` | `27600800` |
| `StickyFault_OverSupplyV` | `274e0800` |
| `StickyFault_ProcTemp` | `27150800` |
| `StickyFault_RemoteSensorDataInvalid` | `27660800` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0800` |
| `StickyFault_RemoteSensorReset` | `27450800` |
| `StickyFault_ReverseHardLimit` | `27540800` |
| `StickyFault_ReverseSoftLimit` | `275a0800` |
| `StickyFault_RotorFault1` | `27a20800` |
| `StickyFault_RotorFault2` | `27a50800` |
| `StickyFault_StaticBrakeDisabled` | `27750800` |
| `StickyFault_StatorCurrLimit` | `276c0800` |
| `StickyFault_SupplyCurrLimit` | `276f0800` |
| `StickyFault_Undervoltage` | `271b0800` |
| `StickyFault_UnlicensedFeatureInUse` | `27210800` |
| `StickyFault_UnstableSupplyV` | `27510800` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720800` |
| `SupplyCurrent` | `6f40800` |
| `SupplyVoltage` | `6f50800` |
| `TorqueCurrent` | `6f20800` |
| `Velocity` | `6fd0800` |
| `Version` | `2e20800` |
| `VersionBugfix` | `2e00800` |
| `VersionBuild` | `2e10800` |
| `VersionMajor` | `2de0800` |
| `VersionMinor` | `2df0800` |

### `TXCMP1_E1_rio_2026-04-18_15-19-53.hoot`

_443 signals._

#### `Other`

| Signal | Hex ID |
|---|---|
| `AllianceStation` | `5ff00` |
| `RobotEnable` | `1ff00` |
| `RobotMode` | `4ff00` |

#### `TalonFX-12`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0c00` |
| `AncillaryDeviceTemp` | `82b0c00` |
| `AppliedRotorPolarity` | `6ef0c00` |
| `BridgeOutput` | `7ab0c00` |
| `ClosedLoopSlot` | `7220c00` |
| `ConnectedMotor` | `8450c00` |
| `ControlMode` | `7070c00` |
| `DeviceEnable` | `7100c00` |
| `DeviceTemp` | `6f60c00` |
| `DutyCycle` | `6f00c00` |
| `FaultField` | `34c0c00` |
| `Fault_BootDuringEnable` | `271d0c00` |
| `Fault_BridgeBrownout` | `27410c00` |
| `Fault_DeviceTemp` | `27170c00` |
| `Fault_ForwardHardLimit` | `27560c00` |
| `Fault_ForwardSoftLimit` | `275c0c00` |
| `Fault_FusedSensorOutOfSync` | `27680c00` |
| `Fault_Hardware` | `27110c00` |
| `Fault_MissingDifferentialFX` | `27470c00` |
| `Fault_MissingHardLimitRemote` | `27620c00` |
| `Fault_MissingSoftLimitRemote` | `275f0c00` |
| `Fault_OverSupplyV` | `274d0c00` |
| `Fault_ProcTemp` | `27140c00` |
| `Fault_RemoteSensorDataInvalid` | `27650c00` |
| `Fault_RemoteSensorPosOverflow` | `274a0c00` |
| `Fault_RemoteSensorReset` | `27440c00` |
| `Fault_ReverseHardLimit` | `27530c00` |
| `Fault_ReverseSoftLimit` | `27590c00` |
| `Fault_RotorFault1` | `27a10c00` |
| `Fault_RotorFault2` | `27a40c00` |
| `Fault_StaticBrakeDisabled` | `27740c00` |
| `Fault_StatorCurrLimit` | `276b0c00` |
| `Fault_SupplyCurrLimit` | `276e0c00` |
| `Fault_Undervoltage` | `271a0c00` |
| `Fault_UnlicensedFeatureInUse` | `27200c00` |
| `Fault_UnstableSupplyV` | `27500c00` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710c00` |
| `ForwardLimit` | `6ed0c00` |
| `IsProLicensed` | `8040c00` |
| `MotionMagicAtTarget` | `70d0c00` |
| `MotionMagicIsRunning` | `70e0c00` |
| `MotorKT` | `7520c00` |
| `MotorKV` | `7530c00` |
| `MotorOutputStatus` | `7260c00` |
| `MotorStallCurrent` | `7540c00` |
| `MotorVoltage` | `6ec0c00` |
| `PIDDutyCycle_DerivativeOutput` | `71c0c00` |
| `PIDDutyCycle_FeedForward` | `7040c00` |
| `PIDDutyCycle_IntegratedAccum` | `7010c00` |
| `PIDDutyCycle_Output` | `71f0c00` |
| `PIDDutyCycle_ProportionalOutput` | `7190c00` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0c00` |
| `PIDMotorVoltage_FeedForward` | `7050c00` |
| `PIDMotorVoltage_IntegratedAccum` | `7020c00` |
| `PIDMotorVoltage_Output` | `7200c00` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0c00` |
| `PIDPosition_ClosedLoopError` | `7140c00` |
| `PIDPosition_Reference` | `7120c00` |
| `PIDPosition_ReferenceSlope` | `7230c00` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0c00` |
| `PIDTorqueCurrent_FeedForward` | `7060c00` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030c00` |
| `PIDTorqueCurrent_Output` | `7210c00` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0c00` |
| `PIDVelocity_ClosedLoopError` | `7150c00` |
| `PIDVelocity_Reference` | `7130c00` |
| `PIDVelocity_ReferenceSlope` | `7240c00` |
| `Position` | `6fe0c00` |
| `ProcessorTemp` | `6f70c00` |
| `ReverseLimit` | `6ee0c00` |
| `RobotEnable` | `70f0c00` |
| `RotorPosition` | `6fa0c00` |
| `RotorVelocity` | `6f90c00` |
| `StatorCurrent` | `6f30c00` |
| `StickyFaultField` | `34d0c00` |
| `StickyFault_BootDuringEnable` | `271e0c00` |
| `StickyFault_BridgeBrownout` | `27420c00` |
| `StickyFault_DeviceTemp` | `27180c00` |
| `StickyFault_ForwardHardLimit` | `27570c00` |
| `StickyFault_ForwardSoftLimit` | `275d0c00` |
| `StickyFault_FusedSensorOutOfSync` | `27690c00` |
| `StickyFault_Hardware` | `27120c00` |
| `StickyFault_MissingDifferentialFX` | `27480c00` |
| `StickyFault_MissingHardLimitRemote` | `27630c00` |
| `StickyFault_MissingSoftLimitRemote` | `27600c00` |
| `StickyFault_OverSupplyV` | `274e0c00` |
| `StickyFault_ProcTemp` | `27150c00` |
| `StickyFault_RemoteSensorDataInvalid` | `27660c00` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0c00` |
| `StickyFault_RemoteSensorReset` | `27450c00` |
| `StickyFault_ReverseHardLimit` | `27540c00` |
| `StickyFault_ReverseSoftLimit` | `275a0c00` |
| `StickyFault_RotorFault1` | `27a20c00` |
| `StickyFault_RotorFault2` | `27a50c00` |
| `StickyFault_StaticBrakeDisabled` | `27750c00` |
| `StickyFault_StatorCurrLimit` | `276c0c00` |
| `StickyFault_SupplyCurrLimit` | `276f0c00` |
| `StickyFault_Undervoltage` | `271b0c00` |
| `StickyFault_UnlicensedFeatureInUse` | `27210c00` |
| `StickyFault_UnstableSupplyV` | `27510c00` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720c00` |
| `SupplyCurrent` | `6f40c00` |
| `SupplyVoltage` | `6f50c00` |
| `TorqueCurrent` | `6f20c00` |
| `Velocity` | `6fd0c00` |
| `Version` | `2e20c00` |
| `VersionBugfix` | `2e00c00` |
| `VersionBuild` | `2e10c00` |
| `VersionMajor` | `2de0c00` |
| `VersionMinor` | `2df0c00` |

#### `TalonFX-13`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0d00` |
| `AncillaryDeviceTemp` | `82b0d00` |
| `AppliedRotorPolarity` | `6ef0d00` |
| `BridgeOutput` | `7ab0d00` |
| `ClosedLoopSlot` | `7220d00` |
| `ConnectedMotor` | `8450d00` |
| `ControlMode` | `7070d00` |
| `DeviceEnable` | `7100d00` |
| `DeviceTemp` | `6f60d00` |
| `DutyCycle` | `6f00d00` |
| `FaultField` | `34c0d00` |
| `Fault_BootDuringEnable` | `271d0d00` |
| `Fault_BridgeBrownout` | `27410d00` |
| `Fault_DeviceTemp` | `27170d00` |
| `Fault_ForwardHardLimit` | `27560d00` |
| `Fault_ForwardSoftLimit` | `275c0d00` |
| `Fault_FusedSensorOutOfSync` | `27680d00` |
| `Fault_Hardware` | `27110d00` |
| `Fault_MissingDifferentialFX` | `27470d00` |
| `Fault_MissingHardLimitRemote` | `27620d00` |
| `Fault_MissingSoftLimitRemote` | `275f0d00` |
| `Fault_OverSupplyV` | `274d0d00` |
| `Fault_ProcTemp` | `27140d00` |
| `Fault_RemoteSensorDataInvalid` | `27650d00` |
| `Fault_RemoteSensorPosOverflow` | `274a0d00` |
| `Fault_RemoteSensorReset` | `27440d00` |
| `Fault_ReverseHardLimit` | `27530d00` |
| `Fault_ReverseSoftLimit` | `27590d00` |
| `Fault_RotorFault1` | `27a10d00` |
| `Fault_RotorFault2` | `27a40d00` |
| `Fault_StaticBrakeDisabled` | `27740d00` |
| `Fault_StatorCurrLimit` | `276b0d00` |
| `Fault_SupplyCurrLimit` | `276e0d00` |
| `Fault_Undervoltage` | `271a0d00` |
| `Fault_UnlicensedFeatureInUse` | `27200d00` |
| `Fault_UnstableSupplyV` | `27500d00` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710d00` |
| `ForwardLimit` | `6ed0d00` |
| `IsProLicensed` | `8040d00` |
| `MotionMagicAtTarget` | `70d0d00` |
| `MotionMagicIsRunning` | `70e0d00` |
| `MotorKT` | `7520d00` |
| `MotorKV` | `7530d00` |
| `MotorOutputStatus` | `7260d00` |
| `MotorStallCurrent` | `7540d00` |
| `MotorVoltage` | `6ec0d00` |
| `PIDDutyCycle_DerivativeOutput` | `71c0d00` |
| `PIDDutyCycle_FeedForward` | `7040d00` |
| `PIDDutyCycle_IntegratedAccum` | `7010d00` |
| `PIDDutyCycle_Output` | `71f0d00` |
| `PIDDutyCycle_ProportionalOutput` | `7190d00` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0d00` |
| `PIDMotorVoltage_FeedForward` | `7050d00` |
| `PIDMotorVoltage_IntegratedAccum` | `7020d00` |
| `PIDMotorVoltage_Output` | `7200d00` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0d00` |
| `PIDPosition_ClosedLoopError` | `7140d00` |
| `PIDPosition_Reference` | `7120d00` |
| `PIDPosition_ReferenceSlope` | `7230d00` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0d00` |
| `PIDTorqueCurrent_FeedForward` | `7060d00` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030d00` |
| `PIDTorqueCurrent_Output` | `7210d00` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0d00` |
| `PIDVelocity_ClosedLoopError` | `7150d00` |
| `PIDVelocity_Reference` | `7130d00` |
| `PIDVelocity_ReferenceSlope` | `7240d00` |
| `Position` | `6fe0d00` |
| `ProcessorTemp` | `6f70d00` |
| `ReverseLimit` | `6ee0d00` |
| `RobotEnable` | `70f0d00` |
| `RotorPosition` | `6fa0d00` |
| `RotorVelocity` | `6f90d00` |
| `StatorCurrent` | `6f30d00` |
| `StickyFaultField` | `34d0d00` |
| `StickyFault_BootDuringEnable` | `271e0d00` |
| `StickyFault_BridgeBrownout` | `27420d00` |
| `StickyFault_DeviceTemp` | `27180d00` |
| `StickyFault_ForwardHardLimit` | `27570d00` |
| `StickyFault_ForwardSoftLimit` | `275d0d00` |
| `StickyFault_FusedSensorOutOfSync` | `27690d00` |
| `StickyFault_Hardware` | `27120d00` |
| `StickyFault_MissingDifferentialFX` | `27480d00` |
| `StickyFault_MissingHardLimitRemote` | `27630d00` |
| `StickyFault_MissingSoftLimitRemote` | `27600d00` |
| `StickyFault_OverSupplyV` | `274e0d00` |
| `StickyFault_ProcTemp` | `27150d00` |
| `StickyFault_RemoteSensorDataInvalid` | `27660d00` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0d00` |
| `StickyFault_RemoteSensorReset` | `27450d00` |
| `StickyFault_ReverseHardLimit` | `27540d00` |
| `StickyFault_ReverseSoftLimit` | `275a0d00` |
| `StickyFault_RotorFault1` | `27a20d00` |
| `StickyFault_RotorFault2` | `27a50d00` |
| `StickyFault_StaticBrakeDisabled` | `27750d00` |
| `StickyFault_StatorCurrLimit` | `276c0d00` |
| `StickyFault_SupplyCurrLimit` | `276f0d00` |
| `StickyFault_Undervoltage` | `271b0d00` |
| `StickyFault_UnlicensedFeatureInUse` | `27210d00` |
| `StickyFault_UnstableSupplyV` | `27510d00` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720d00` |
| `SupplyCurrent` | `6f40d00` |
| `SupplyVoltage` | `6f50d00` |
| `TorqueCurrent` | `6f20d00` |
| `Velocity` | `6fd0d00` |
| `Version` | `2e20d00` |
| `VersionBugfix` | `2e00d00` |
| `VersionBuild` | `2e10d00` |
| `VersionMajor` | `2de0d00` |
| `VersionMinor` | `2df0d00` |

#### `TalonFX-14`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0e00` |
| `AncillaryDeviceTemp` | `82b0e00` |
| `AppliedRotorPolarity` | `6ef0e00` |
| `BridgeOutput` | `7ab0e00` |
| `ClosedLoopSlot` | `7220e00` |
| `ConnectedMotor` | `8450e00` |
| `ControlMode` | `7070e00` |
| `DeviceEnable` | `7100e00` |
| `DeviceTemp` | `6f60e00` |
| `DutyCycle` | `6f00e00` |
| `FaultField` | `34c0e00` |
| `Fault_BootDuringEnable` | `271d0e00` |
| `Fault_BridgeBrownout` | `27410e00` |
| `Fault_DeviceTemp` | `27170e00` |
| `Fault_ForwardHardLimit` | `27560e00` |
| `Fault_ForwardSoftLimit` | `275c0e00` |
| `Fault_FusedSensorOutOfSync` | `27680e00` |
| `Fault_Hardware` | `27110e00` |
| `Fault_MissingDifferentialFX` | `27470e00` |
| `Fault_MissingHardLimitRemote` | `27620e00` |
| `Fault_MissingSoftLimitRemote` | `275f0e00` |
| `Fault_OverSupplyV` | `274d0e00` |
| `Fault_ProcTemp` | `27140e00` |
| `Fault_RemoteSensorDataInvalid` | `27650e00` |
| `Fault_RemoteSensorPosOverflow` | `274a0e00` |
| `Fault_RemoteSensorReset` | `27440e00` |
| `Fault_ReverseHardLimit` | `27530e00` |
| `Fault_ReverseSoftLimit` | `27590e00` |
| `Fault_RotorFault1` | `27a10e00` |
| `Fault_RotorFault2` | `27a40e00` |
| `Fault_StaticBrakeDisabled` | `27740e00` |
| `Fault_StatorCurrLimit` | `276b0e00` |
| `Fault_SupplyCurrLimit` | `276e0e00` |
| `Fault_Undervoltage` | `271a0e00` |
| `Fault_UnlicensedFeatureInUse` | `27200e00` |
| `Fault_UnstableSupplyV` | `27500e00` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710e00` |
| `ForwardLimit` | `6ed0e00` |
| `IsProLicensed` | `8040e00` |
| `MotionMagicAtTarget` | `70d0e00` |
| `MotionMagicIsRunning` | `70e0e00` |
| `MotorKT` | `7520e00` |
| `MotorKV` | `7530e00` |
| `MotorOutputStatus` | `7260e00` |
| `MotorStallCurrent` | `7540e00` |
| `MotorVoltage` | `6ec0e00` |
| `PIDDutyCycle_DerivativeOutput` | `71c0e00` |
| `PIDDutyCycle_FeedForward` | `7040e00` |
| `PIDDutyCycle_IntegratedAccum` | `7010e00` |
| `PIDDutyCycle_Output` | `71f0e00` |
| `PIDDutyCycle_ProportionalOutput` | `7190e00` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0e00` |
| `PIDMotorVoltage_FeedForward` | `7050e00` |
| `PIDMotorVoltage_IntegratedAccum` | `7020e00` |
| `PIDMotorVoltage_Output` | `7200e00` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0e00` |
| `PIDPosition_ClosedLoopError` | `7140e00` |
| `PIDPosition_Reference` | `7120e00` |
| `PIDPosition_ReferenceSlope` | `7230e00` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0e00` |
| `PIDTorqueCurrent_FeedForward` | `7060e00` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030e00` |
| `PIDTorqueCurrent_Output` | `7210e00` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0e00` |
| `PIDVelocity_ClosedLoopError` | `7150e00` |
| `PIDVelocity_Reference` | `7130e00` |
| `PIDVelocity_ReferenceSlope` | `7240e00` |
| `Position` | `6fe0e00` |
| `ProcessorTemp` | `6f70e00` |
| `ReverseLimit` | `6ee0e00` |
| `RobotEnable` | `70f0e00` |
| `RotorPosition` | `6fa0e00` |
| `RotorVelocity` | `6f90e00` |
| `StatorCurrent` | `6f30e00` |
| `StickyFaultField` | `34d0e00` |
| `StickyFault_BootDuringEnable` | `271e0e00` |
| `StickyFault_BridgeBrownout` | `27420e00` |
| `StickyFault_DeviceTemp` | `27180e00` |
| `StickyFault_ForwardHardLimit` | `27570e00` |
| `StickyFault_ForwardSoftLimit` | `275d0e00` |
| `StickyFault_FusedSensorOutOfSync` | `27690e00` |
| `StickyFault_Hardware` | `27120e00` |
| `StickyFault_MissingDifferentialFX` | `27480e00` |
| `StickyFault_MissingHardLimitRemote` | `27630e00` |
| `StickyFault_MissingSoftLimitRemote` | `27600e00` |
| `StickyFault_OverSupplyV` | `274e0e00` |
| `StickyFault_ProcTemp` | `27150e00` |
| `StickyFault_RemoteSensorDataInvalid` | `27660e00` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0e00` |
| `StickyFault_RemoteSensorReset` | `27450e00` |
| `StickyFault_ReverseHardLimit` | `27540e00` |
| `StickyFault_ReverseSoftLimit` | `275a0e00` |
| `StickyFault_RotorFault1` | `27a20e00` |
| `StickyFault_RotorFault2` | `27a50e00` |
| `StickyFault_StaticBrakeDisabled` | `27750e00` |
| `StickyFault_StatorCurrLimit` | `276c0e00` |
| `StickyFault_SupplyCurrLimit` | `276f0e00` |
| `StickyFault_Undervoltage` | `271b0e00` |
| `StickyFault_UnlicensedFeatureInUse` | `27210e00` |
| `StickyFault_UnstableSupplyV` | `27510e00` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720e00` |
| `SupplyCurrent` | `6f40e00` |
| `SupplyVoltage` | `6f50e00` |
| `TorqueCurrent` | `6f20e00` |
| `Velocity` | `6fd0e00` |
| `Version` | `2e20e00` |
| `VersionBugfix` | `2e00e00` |
| `VersionBuild` | `2e10e00` |
| `VersionMajor` | `2de0e00` |
| `VersionMinor` | `2df0e00` |

#### `TalonFX-15`

| Signal | Hex ID |
|---|---|
| `Acceleration` | `6ff0f00` |
| `AncillaryDeviceTemp` | `82b0f00` |
| `AppliedRotorPolarity` | `6ef0f00` |
| `BridgeOutput` | `7ab0f00` |
| `ClosedLoopSlot` | `7220f00` |
| `ConnectedMotor` | `8450f00` |
| `ControlMode` | `7070f00` |
| `DeviceEnable` | `7100f00` |
| `DeviceTemp` | `6f60f00` |
| `DutyCycle` | `6f00f00` |
| `FaultField` | `34c0f00` |
| `Fault_BootDuringEnable` | `271d0f00` |
| `Fault_BridgeBrownout` | `27410f00` |
| `Fault_DeviceTemp` | `27170f00` |
| `Fault_ForwardHardLimit` | `27560f00` |
| `Fault_ForwardSoftLimit` | `275c0f00` |
| `Fault_FusedSensorOutOfSync` | `27680f00` |
| `Fault_Hardware` | `27110f00` |
| `Fault_MissingDifferentialFX` | `27470f00` |
| `Fault_MissingHardLimitRemote` | `27620f00` |
| `Fault_MissingSoftLimitRemote` | `275f0f00` |
| `Fault_OverSupplyV` | `274d0f00` |
| `Fault_ProcTemp` | `27140f00` |
| `Fault_RemoteSensorDataInvalid` | `27650f00` |
| `Fault_RemoteSensorPosOverflow` | `274a0f00` |
| `Fault_RemoteSensorReset` | `27440f00` |
| `Fault_ReverseHardLimit` | `27530f00` |
| `Fault_ReverseSoftLimit` | `27590f00` |
| `Fault_RotorFault1` | `27a10f00` |
| `Fault_RotorFault2` | `27a40f00` |
| `Fault_StaticBrakeDisabled` | `27740f00` |
| `Fault_StatorCurrLimit` | `276b0f00` |
| `Fault_SupplyCurrLimit` | `276e0f00` |
| `Fault_Undervoltage` | `271a0f00` |
| `Fault_UnlicensedFeatureInUse` | `27200f00` |
| `Fault_UnstableSupplyV` | `27500f00` |
| `Fault_UsingFusedCANcoderWhileUnlicensed` | `27710f00` |
| `ForwardLimit` | `6ed0f00` |
| `IsProLicensed` | `8040f00` |
| `MotionMagicAtTarget` | `70d0f00` |
| `MotionMagicIsRunning` | `70e0f00` |
| `MotorKT` | `7520f00` |
| `MotorKV` | `7530f00` |
| `MotorOutputStatus` | `7260f00` |
| `MotorStallCurrent` | `7540f00` |
| `MotorVoltage` | `6ec0f00` |
| `PIDDutyCycle_DerivativeOutput` | `71c0f00` |
| `PIDDutyCycle_FeedForward` | `7040f00` |
| `PIDDutyCycle_IntegratedAccum` | `7010f00` |
| `PIDDutyCycle_Output` | `71f0f00` |
| `PIDDutyCycle_ProportionalOutput` | `7190f00` |
| `PIDMotorVoltage_DerivativeOutput` | `71d0f00` |
| `PIDMotorVoltage_FeedForward` | `7050f00` |
| `PIDMotorVoltage_IntegratedAccum` | `7020f00` |
| `PIDMotorVoltage_Output` | `7200f00` |
| `PIDMotorVoltage_ProportionalOutput` | `71a0f00` |
| `PIDPosition_ClosedLoopError` | `7140f00` |
| `PIDPosition_Reference` | `7120f00` |
| `PIDPosition_ReferenceSlope` | `7230f00` |
| `PIDTorqueCurrent_DerivativeOutput` | `71e0f00` |
| `PIDTorqueCurrent_FeedForward` | `7060f00` |
| `PIDTorqueCurrent_IntegratedAccum` | `7030f00` |
| `PIDTorqueCurrent_Output` | `7210f00` |
| `PIDTorqueCurrent_ProportionalOutput` | `71b0f00` |
| `PIDVelocity_ClosedLoopError` | `7150f00` |
| `PIDVelocity_Reference` | `7130f00` |
| `PIDVelocity_ReferenceSlope` | `7240f00` |
| `Position` | `6fe0f00` |
| `ProcessorTemp` | `6f70f00` |
| `ReverseLimit` | `6ee0f00` |
| `RobotEnable` | `70f0f00` |
| `RotorPosition` | `6fa0f00` |
| `RotorVelocity` | `6f90f00` |
| `StatorCurrent` | `6f30f00` |
| `StickyFaultField` | `34d0f00` |
| `StickyFault_BootDuringEnable` | `271e0f00` |
| `StickyFault_BridgeBrownout` | `27420f00` |
| `StickyFault_DeviceTemp` | `27180f00` |
| `StickyFault_ForwardHardLimit` | `27570f00` |
| `StickyFault_ForwardSoftLimit` | `275d0f00` |
| `StickyFault_FusedSensorOutOfSync` | `27690f00` |
| `StickyFault_Hardware` | `27120f00` |
| `StickyFault_MissingDifferentialFX` | `27480f00` |
| `StickyFault_MissingHardLimitRemote` | `27630f00` |
| `StickyFault_MissingSoftLimitRemote` | `27600f00` |
| `StickyFault_OverSupplyV` | `274e0f00` |
| `StickyFault_ProcTemp` | `27150f00` |
| `StickyFault_RemoteSensorDataInvalid` | `27660f00` |
| `StickyFault_RemoteSensorPosOverflow` | `274b0f00` |
| `StickyFault_RemoteSensorReset` | `27450f00` |
| `StickyFault_ReverseHardLimit` | `27540f00` |
| `StickyFault_ReverseSoftLimit` | `275a0f00` |
| `StickyFault_RotorFault1` | `27a20f00` |
| `StickyFault_RotorFault2` | `27a50f00` |
| `StickyFault_StaticBrakeDisabled` | `27750f00` |
| `StickyFault_StatorCurrLimit` | `276c0f00` |
| `StickyFault_SupplyCurrLimit` | `276f0f00` |
| `StickyFault_Undervoltage` | `271b0f00` |
| `StickyFault_UnlicensedFeatureInUse` | `27210f00` |
| `StickyFault_UnstableSupplyV` | `27510f00` |
| `StickyFault_UsingFusedCANcoderWhileUnlicensed` | `27720f00` |
| `SupplyCurrent` | `6f40f00` |
| `SupplyVoltage` | `6f50f00` |
| `TorqueCurrent` | `6f20f00` |
| `Velocity` | `6fd0f00` |
| `Version` | `2e20f00` |
| `VersionBugfix` | `2e00f00` |
| `VersionBuild` | `2e10f00` |
| `VersionMajor` | `2de0f00` |
| `VersionMinor` | `2df0f00` |
