import importlib
import os
import sys

import bpy

from albam.blender_ui import CLASSES_TO_REGISTER
from albam.blender_ui.data import AlbamData


bl_info = {
    "name": "Albam",
    "author": "Sebastian A. Brachi",
    "version": (0, 3, 6),
    "blender": (2, 80, 0),
    "location": "Properties Panel",
    "description": "Import-Export multiple video-game formats",
    "category": "Import-Export",
}

ALBAM_DIR = os.path.dirname(__file__)
VENDOR_DIR = os.path.join(ALBAM_DIR, "albam_vendor")


def register():
    sys.path.insert(0, VENDOR_DIR)
    # Load registered functions into the blender_registry
    importlib.import_module("albam.engines.mtfw.archive")
    importlib.import_module("albam.engines.mtfw.mesh")

    for cls in CLASSES_TO_REGISTER:
        bpy.utils.register_class(cls)

    bpy.types.Scene.albam = bpy.props.PointerProperty(type=AlbamData)


def unregister():
    for cls in reversed(CLASSES_TO_REGISTER):
        bpy.utils.unregister_class(cls)
    sys.path.remove(VENDOR_DIR)
