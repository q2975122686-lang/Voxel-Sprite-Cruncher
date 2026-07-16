import bpy, os

# Weapon mapping: our weapon -> blender mesh
weapon_map = {
    "wooden_club": "WoodenBat_Barbed",
    "energy_blade": "Knife",
    "em_gun": "Pistol",
    "shock_cannon": "Shotgun",
    "drone": "SMG",
    "purifier": "Rifle",
}

arm = bpy.data.objects["CharacterArmature"]
matt = bpy.data.objects["Matt"]

for wname, wmesh in weapon_map.items():
    weapon = bpy.data.objects.get(wmesh)
    if not weapon:
        print(f"SKIP {wname}: {wmesh} not found")
        continue
    
    # Deselect all, select arm+matt+weapon
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    matt.select_set(True)
    weapon.select_set(True)
    bpy.context.view_layer.objects.active = arm
    
    out = rf"D:\GodotProjects\3d转2d管线\character\player_{wname}.glb"
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True,
        export_animations=True, export_skins=True, export_apply=False)
    
    sz = os.path.getsize(out)
    print(f"GLB exported: {wname} ({sz} bytes)")

print("DONE")
