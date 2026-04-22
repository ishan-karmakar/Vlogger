# -*- coding: utf-8 -*-
"""
Canonical CAN device mapping for analysis scripts.

Shared by all scripts in analysis/ that need to translate Phoenix hoot-log
device names (e.g. "TalonFX-12/StatorCurrent") to the higher-level motor
labels used in the NT-logged wpilog series (e.g. "Left Intake Motor").

===============================================================================
UPDATE WHEN THE ROBOT CAN IDs CHANGE
===============================================================================
Source of truth: `src/main/include/constants/Constants.h` in the robot repo
(namespace `CANIDs`).  Keep the comment next to each entry in sync with that
file so it's obvious what to update.

Entries are `("DeviceKind", can_id): "<label>"` — the DeviceKind values
("TalonFX", "CANcoder", "Pigeon2", "CANdle", "CANrange") match what
owlet --scan prints in the hoot log.

After you update CAN_DEVICES, the SUBSYSTEMS mapping below is the only
other thing you should need to touch — it groups labels into logical
subsystems for analysis scripts that want "all intake motors" etc.
===============================================================================
"""

# (kind, can_id) -> analyzer label
CAN_DEVICES = {
    # --- Swerve drive (Canivore bus) -----------------------------------------
    # DRIVE_CANS   = {2, 4, 6, 8}   (front-left, front-right, back-left, back-right)
    # AZIMUTH_CANS = {1, 3, 5, 7}
    ("TalonFX",  1): "Swerve Azimuth FL",
    ("TalonFX",  2): "Swerve Drive FL",
    ("TalonFX",  3): "Swerve Azimuth FR",
    ("TalonFX",  4): "Swerve Drive FR",
    ("TalonFX",  5): "Swerve Azimuth BL",
    ("TalonFX",  6): "Swerve Drive BL",
    ("TalonFX",  7): "Swerve Azimuth BR",
    ("TalonFX",  8): "Swerve Drive BR",

    # --- Intake subsystem (RIO bus) ------------------------------------------
    ("TalonFX", 11): "Intake Pivot",
    ("TalonFX", 12): "Left Intake",
    ("TalonFX", 13): "Right Intake",
    ("TalonFX", 14): "Left Hopper",
    ("TalonFX", 15): "Right Hopper",

    # --- Shooter (Canivore bus) ----------------------------------------------
    ("TalonFX", 30): "Flywheel Left",
    ("TalonFX", 31): "Flywheel Right One",
    ("TalonFX", 32): "Flywheel Right Two",
    ("TalonFX", 33): "Hood",
    ("CANcoder", 26): "Hood Encoder",

    # --- Feeder (Canivore bus) -----------------------------------------------
    ("TalonFX", 51): "Left Feeder",
    ("TalonFX", 52): "Right Feeder",
    ("CANrange", 40): "Feeder CANrange",

    # --- Climber (bus not specified in constants header) ---------------------
    ("TalonFX", 45): "Climber",

    # --- Swerve sensors ------------------------------------------------------
    ("CANcoder", 20): "Swerve Encoder FL",
    ("CANcoder", 21): "Swerve Encoder FR",
    ("CANcoder", 22): "Swerve Encoder BL",
    ("CANcoder", 23): "Swerve Encoder BR",

    # --- Chassis ------------------------------------------------------------
    ("Pigeon2", 61): "Pigeon",
    ("CANdle",  60): "CANdle",
}

# Inverse: label -> (kind, id)
CAN_DEVICES_BY_LABEL = {v: k for k, v in CAN_DEVICES.items()}

# Which labels belong to which subsystem. Each value is a list so consumers
# can iterate in a predictable order.
SUBSYSTEMS = {
    "swerve_drive":   ["Swerve Drive FL", "Swerve Drive FR",
                        "Swerve Drive BL", "Swerve Drive BR"],
    "swerve_azimuth": ["Swerve Azimuth FL", "Swerve Azimuth FR",
                        "Swerve Azimuth BL", "Swerve Azimuth BR"],
    "intake":         ["Left Intake", "Right Intake"],
    "hopper":         ["Left Hopper", "Right Hopper"],
    "feeder":         ["Left Feeder", "Right Feeder"],
    "flywheel":       ["Flywheel Left", "Flywheel Right One", "Flywheel Right Two"],
    "shooter_misc":   ["Hood"],
    "intake_pivot":   ["Intake Pivot"],
    "climber":        ["Climber"],
}

# Which CAN bus each label lives on (informational; used to hint which hoot
# file to look in — the .hoot file name typically contains "_rio_" for the
# RIO bus and a device serial for the Canivore bus).
CAN_BUSES = {
    "rio":      {"Intake Pivot", "Left Intake", "Right Intake",
                 "Left Hopper", "Right Hopper"},
    # Everything else is assumed to be on the Canivore bus.
}

def label_for(kind, can_id):
    """Return the analyzer label for (device_kind, can_id), or None if unmapped."""
    return CAN_DEVICES.get((kind, int(can_id)))

def labels_for_subsystem(name):
    """List of motor labels in a subsystem (e.g. 'intake', 'feeder')."""
    return list(SUBSYSTEMS.get(name, []))

def bus_for(label):
    """Return 'rio' or 'canivore' based on CAN_BUSES membership."""
    if label in CAN_BUSES.get("rio", set()):
        return "rio"
    return "canivore"
