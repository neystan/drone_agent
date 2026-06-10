"""集中定义函数调用工具的 schema。"""

from __future__ import annotations


TAKEOFF_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "takeoff",
        "description": "Take off the UAV to a target height in meters.",
        "parameters": {
            "type": "object",
            "properties": {
                "height": {
                    "type": "number",
                    "description": "Target takeoff height in meters. Valid range is 0 to 10.",
                }
            },
            "required": ["height"],
            "additionalProperties": False,
        },
    },
}

LAND_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "land",
        "description": "Land the UAV safely at the current location.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}

DISARM_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "disarm",
        "description": "Disarm the UAV motors.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}

TIMER_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "timer",
        "description": "Wait for a specified number of seconds.",
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "integer",
                    "description": "Number of seconds to wait. Must be between 1 and 600.",
                }
            },
            "required": ["seconds"],
            "additionalProperties": False,
        },
    },
}

HOVER_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "hover",
        "description": "Switch the UAV to AUTO_LOITER hover mode at the current location.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}

RETURN_HOME_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "return_home",
        "description": "Command the UAV to return to home using PX4 RTL mode.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}

CURRENT_POSITION_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "current_position_status",
        "description": "Get the UAV current local position in NED coordinates.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}

BATTERY_STATUS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "battery_status",
        "description": "Get the UAV battery status.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}

FLIGHT_MODE_STATUS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "flight_mode_status",
        "description": "Get the UAV current flight mode and basic state.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}

ROTATE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "rotate",
        "description": "Rotate the UAV left or right by a specified angle in degrees while holding the current position.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["left", "right"],
                    "description": "Rotation direction. Use 'left' for counterclockwise and 'right' for clockwise.",
                },
                "degrees": {
                    "type": "number",
                    "description": "Rotation angle in degrees. Must be between 0 and 360.",
                },
            },
            "required": ["direction", "degrees"],
            "additionalProperties": False,
        },
    },
}

MOVE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "move",
        "description": "Move the UAV by a relative offset in the body FRD frame in meters.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {
                    "type": "number",
                    "description": "Body-frame x offset in meters. Positive is forward, negative is backward. Valid range is -20 to 20.",
                },
                "y": {
                    "type": "number",
                    "description": "Body-frame y offset in meters. Positive is right, negative is left. Valid range is -20 to 20.",
                },
                "z": {
                    "type": "number",
                    "description": "Body-frame z offset in meters. Positive is down, negative is up. Valid range is -10 to 10.",
                },
            },
            "required": ["x", "y", "z"],
            "additionalProperties": False,
        },
    },
}

TAKE_PHOTO_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "take_photo",
        "description": "Capture one RGB photo from the front camera and save it to a local file.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}

ANALYZE_VIEW_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "analyze_view",
        "description": "Analyze the current camera view. Optionally search for a target in the scene.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_description": {
                    "type": "string",
                    "description": "Optional target to search for in the current camera view. Leave empty to only describe the scene.",
                }
            },
            "additionalProperties": False,
        },
    },
}

TOOL_SCHEMAS = [
    TAKEOFF_TOOL_SCHEMA,
    LAND_TOOL_SCHEMA,
    DISARM_TOOL_SCHEMA,
    TIMER_TOOL_SCHEMA,
    HOVER_TOOL_SCHEMA,
    RETURN_HOME_TOOL_SCHEMA,
    CURRENT_POSITION_TOOL_SCHEMA,
    BATTERY_STATUS_TOOL_SCHEMA,
    FLIGHT_MODE_STATUS_TOOL_SCHEMA,
    ROTATE_TOOL_SCHEMA,
    MOVE_TOOL_SCHEMA,
    TAKE_PHOTO_TOOL_SCHEMA,
    ANALYZE_VIEW_TOOL_SCHEMA,
]


def get_tool_schemas() -> list[dict]:
    """返回注册给大模型的全部工具 schema。"""
    return list(TOOL_SCHEMAS)
