import bpy, os

bpy.ops.object.select_all(action='SELECT')
for name in ["CharacterArmature", "Matt"]:
    o = bpy.data.objects.get(name)
    if o: o.select_set(True)
bpy.context.view_layer.objects.active = bpy.data.objects.get("CharacterArmature")

out = os.path.join(os.path.dirname(bpy.data.filepath), "..", "glTF", "Characters_Matt_Animations.glb")
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True,
    export_animations=True, export_skins=True, export_apply=False)
print(f"GLB exported: {out} ({os.path.getsize(out)} bytes)")
