import argparse
import json
import math
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    script_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--animations", default="")
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--fps", type=float, default=12.0)
    parser.add_argument("--animation-fps", default="")
    parser.add_argument("--animation-settings", default="{}")
    parser.add_argument("--view-axis", choices=("+x", "-x", "+y", "-y"), default="+x")
    parser.add_argument("--up-axis", choices=("y", "z"), default="z")
    parser.add_argument("--padding", type=float, default=1.18)
    parser.add_argument("--key-light", type=float, default=120.0)
    parser.add_argument("--fill-light", type=float, default=35.0)
    parser.add_argument("--exposure", type=float, default=-0.5)
    parser.add_argument("--list-actions", action="store_true")
    parser.add_argument("--list-materials", action="store_true")
    parser.add_argument("--passes", default="color,normal")
    parser.add_argument("--material-colors", default="{}")
    parser.add_argument("--single-frame", action="store_true")
    return parser.parse_args(script_args)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)


def import_source(source_path):
    suffix = source_path.suffix.lower()
    if suffix in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(source_path))
        return
    if suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(source_path))
        return
    raise RuntimeError(f"Unsupported source format: {suffix}")


def get_armatures():
    return [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]


def get_actions():
    return sorted(list(bpy.data.actions), key=lambda action: action.name.lower())


def print_actions(actions):
    print("SPRITE_PIPELINE_ACTIONS")
    for action in actions:
        start, end = action.frame_range
        print(f"{action.name}\t{start:.2f}\t{end:.2f}")


def color_to_hex(color):
    channels = [max(0, min(255, round(float(channel) * 255))) for channel in color[:3]]
    return "#%02x%02x%02x" % tuple(channels)


def get_material_base_color(material):
    if material.use_nodes and material.node_tree:
        for node in material.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                return tuple(node.inputs["Base Color"].default_value)
    return tuple(material.diffuse_color)


def material_texture_name(material):
    if not material.use_nodes or not material.node_tree:
        return ""
    for node in material.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            return node.image.name
    return ""


def material_usage():
    usage = {material.name: {"polygons": 0, "objects": set()} for material in bpy.data.materials}
    for obj in visible_mesh_objects():
        polygon_counts = {}
        for polygon in obj.data.polygons:
            polygon_counts[polygon.material_index] = polygon_counts.get(polygon.material_index, 0) + 1
        for slot_index, slot in enumerate(obj.material_slots):
            if slot.material is None:
                continue
            entry = usage.setdefault(slot.material.name, {"polygons": 0, "objects": set()})
            count = polygon_counts.get(slot_index, 0)
            entry["polygons"] += count
            if count:
                entry["objects"].add(obj.name)
    return usage


def print_materials():
    usage = material_usage()
    print("SPRITE_PIPELINE_MATERIALS")
    for material in sorted(bpy.data.materials, key=lambda item: item.name.lower()):
        entry = usage.get(material.name, {"polygons": 0, "objects": set()})
        texture = material_texture_name(material).replace("\t", " ")
        print(f"{material.name}\t{color_to_hex(get_material_base_color(material))}\t{entry['polygons']}\t{len(entry['objects'])}\t{texture}")


def select_actions(actions, requested_names):
    if not requested_names:
        return actions
    by_name = {action.name.casefold(): action for action in actions}
    selected = []
    missing = []
    for name in requested_names:
        action = by_name.get(name.casefold())
        if action is None:
            missing.append(name)
        else:
            selected.append(action)
    if missing:
        available = ", ".join(action.name for action in actions)
        raise RuntimeError(f"Animations not found: {', '.join(missing)}. Available: {available}")
    return selected


def parse_animation_fps(value):
    result = {}
    for entry in value.split(","):
        if not entry.strip() or "=" not in entry:
            continue
        name, fps_value = entry.split("=", 1)
        result[name.strip().casefold()] = max(float(fps_value), 1.0)
    return result


def assign_action(armatures, action):
    assigned = False
    for armature in armatures:
        armature.animation_data_create()
        try:
            armature.animation_data.action = action
            assigned = True
        except RuntimeError:
            continue
    if not assigned:
        raise RuntimeError(f"Could not assign action '{action.name}' to an armature")


def sample_frames(action, source_fps, target_fps):
    start, end = action.frame_range
    step = max(source_fps / max(target_fps, 1.0), 1.0)
    frames = []
    current = float(start)
    while current <= end + 0.001:
        frame = int(round(current))
        if not frames or frames[-1] != frame:
            frames.append(frame)
        current += step
    final_frame = int(round(end))
    if frames[-1] != final_frame:
        frames.append(final_frame)
    return frames


def is_armature_mesh(obj, armatures):
    if any(modifier.type == "ARMATURE" and modifier.object in armatures for modifier in obj.modifiers):
        return True
    parent = obj.parent
    while parent is not None:
        if parent in armatures:
            return True
        parent = parent.parent
    return False


def visible_mesh_objects(armatures):
    meshes = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and not obj.hide_render and obj.visible_get()
    ]
    # 角色导出文件经常带有碰撞体、参考物或灯光用辅助网格。优先只取
    # 绑定到骨架的网格；没有骨骼绑定网格时才退回到全部可见网格。
    skinned_meshes = [obj for obj in meshes if is_armature_mesh(obj, armatures)]
    return skinned_meshes or meshes


def bounds_for_current_frame(mesh_objects):
    minimum = Vector((math.inf, math.inf, math.inf))
    maximum = Vector((-math.inf, -math.inf, -math.inf))
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in mesh_objects:
        # obj.bound_box 是蒙皮前的静态包围盒，会漏掉挥动的武器、伸出的手
        # 或根骨位移。必须从当前动画帧的 evaluated mesh 读取真实顶点位置。
        evaluated_obj = obj.evaluated_get(depsgraph)
        for vertex in evaluated_obj.data.vertices:
            world_corner = evaluated_obj.matrix_world @ vertex.co
            minimum.x = min(minimum.x, world_corner.x)
            minimum.y = min(minimum.y, world_corner.y)
            minimum.z = min(minimum.z, world_corner.z)
            maximum.x = max(maximum.x, world_corner.x)
            maximum.y = max(maximum.y, world_corner.y)
            maximum.z = max(maximum.z, world_corner.z)
    if not math.isfinite(minimum.x):
        raise RuntimeError("No visible mesh objects found")
    return minimum, maximum


def combined_bounds(armatures, action, frames, mesh_objects):
    assign_action(armatures, action)
    minimum = Vector((math.inf, math.inf, math.inf))
    maximum = Vector((-math.inf, -math.inf, -math.inf))
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        frame_minimum, frame_maximum = bounds_for_current_frame(mesh_objects)
        minimum.x = min(minimum.x, frame_minimum.x)
        minimum.y = min(minimum.y, frame_minimum.y)
        minimum.z = min(minimum.z, frame_minimum.z)
        maximum.x = max(maximum.x, frame_maximum.x)
        maximum.y = max(maximum.y, frame_maximum.y)
        maximum.z = max(maximum.z, frame_maximum.z)
    return minimum, maximum


def look_at(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def camera_location(center, distance, view_axis):
    offsets = {
        "+x": Vector((distance, 0.0, 0.0)),
        "-x": Vector((-distance, 0.0, 0.0)),
        "+y": Vector((0.0, distance, 0.0)),
        "-y": Vector((0.0, -distance, 0.0)),
    }
    return center + offsets[view_axis]


def configure_render(size, exposure):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.filter_size = 0.01
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = exposure
    scene.world.color = (0.035, 0.045, 0.055)


def find_principled(material):
    if not material.use_nodes or not material.node_tree:
        return None
    for node in material.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            return node
    return None


def srgb_channel_to_linear(value):
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def hex_to_linear_rgba(value, fallback):
    hex_value = str(value or "").lstrip("#")
    if len(hex_value) != 6:
        return fallback
    channels = [int(hex_value[index:index + 2], 16) / 255.0 for index in (0, 2, 4)]
    return tuple(srgb_channel_to_linear(channel) for channel in channels) + (1.0,)


def connect_base_color(material, target_input):
    principled = find_principled(material)
    base_input = principled.inputs["Base Color"] if principled else None
    if base_input and base_input.is_linked:
        material.node_tree.links.new(base_input.links[0].from_socket, target_input)
    else:
        target_input.default_value = get_material_base_color(material)


def make_gradient_color(material, style):
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    luminance = nodes.new("ShaderNodeRGBToBW")
    perceived_luminance = nodes.new("ShaderNodeMath")
    perceived_luminance.operation = "POWER"
    perceived_luminance.inputs[1].default_value = 1.0 / 2.2
    gradient = nodes.new("ShaderNodeValToRGB")
    gradient.color_ramp.interpolation = "LINEAR"
    shadow = gradient.color_ramp.elements[0]
    highlight = gradient.color_ramp.elements[1]
    middle = gradient.color_ramp.elements.new(0.5)
    shadow.position = 0.0
    highlight.position = 1.0
    shadow.color = hex_to_linear_rgba(style.get("shadow"), (0.015, 0.015, 0.015, 1.0))
    middle.color = hex_to_linear_rgba(style.get("mid"), (0.215, 0.215, 0.215, 1.0))
    highlight.color = hex_to_linear_rgba(style.get("highlight"), (1.0, 1.0, 1.0, 1.0))
    connect_base_color(material, luminance.inputs["Color"])
    links.new(luminance.outputs["Val"], perceived_luminance.inputs[0])
    links.new(perceived_luminance.outputs[0], gradient.inputs["Fac"])
    return gradient.outputs["Color"]


def make_material_flat(material, override_style):
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    output = next((node for node in nodes if node.type == "OUTPUT_MATERIAL"), None)
    if output is None:
        output = nodes.new("ShaderNodeOutputMaterial")
    for link in list(output.inputs["Surface"].links):
        links.remove(link)

    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Strength"].default_value = 1.0
    if isinstance(override_style, dict) and override_style.get("mode") == "gradient":
        links.new(make_gradient_color(material, override_style), emission.inputs["Color"])
    elif override_style:
        color_value = override_style.get("color") if isinstance(override_style, dict) else override_style
        emission.inputs["Color"].default_value = hex_to_linear_rgba(color_value, get_material_base_color(material))
    else:
        connect_base_color(material, emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])


def apply_flat_materials(material_colors):
    for material in bpy.data.materials:
        make_material_flat(material, material_colors.get(material.name))


def create_normal_material():
    material = bpy.data.materials.new("__SPRITE_NORMAL_PASS__")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    geometry = nodes.new("ShaderNodeNewGeometry")
    transform = nodes.new("ShaderNodeVectorTransform")
    transform.vector_type = "NORMAL"
    transform.convert_from = "WORLD"
    transform.convert_to = "CAMERA"
    flip_z = nodes.new("ShaderNodeVectorMath")
    flip_z.operation = "MULTIPLY"
    flip_z.inputs[1].default_value = (1.0, 1.0, -1.0)
    multiply = nodes.new("ShaderNodeVectorMath")
    multiply.operation = "SCALE"
    multiply.inputs[3].default_value = 0.5
    add = nodes.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    add.inputs[1].default_value = (0.5, 0.5, 0.5)
    links.new(geometry.outputs["Normal"], transform.inputs["Vector"])
    links.new(transform.outputs["Vector"], flip_z.inputs[0])
    links.new(flip_z.outputs["Vector"], multiply.inputs[0])
    links.new(multiply.outputs["Vector"], add.inputs[0])
    links.new(add.outputs["Vector"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def capture_mesh_materials(mesh_objects):
    snapshots = []
    seen_meshes = set()
    for obj in mesh_objects:
        mesh_key = obj.data.as_pointer()
        if mesh_key in seen_meshes:
            continue
        seen_meshes.add(mesh_key)
        snapshots.append((obj.data, list(obj.data.materials)))
    return snapshots


def replace_mesh_materials(snapshots, material):
    for mesh, _materials in snapshots:
        mesh.materials.clear()
        mesh.materials.append(material)


def restore_mesh_materials(snapshots):
    for mesh, materials in snapshots:
        mesh.materials.clear()
        for material in materials:
            mesh.materials.append(material)


def create_flat_id_material(name, color):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = 1.0
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def create_material_id_map(snapshots):
    palette = [
        (1.0, 0.15, 0.15, 1.0),
        (0.15, 1.0, 0.2, 1.0),
        (0.15, 0.35, 1.0, 1.0),
        (1.0, 0.85, 0.1, 1.0),
        (0.9, 0.15, 1.0, 1.0),
        (0.1, 0.95, 1.0, 1.0),
        (1.0, 0.45, 0.08, 1.0),
        (0.55, 0.25, 1.0, 1.0),
    ]
    originals = sorted(
        {material for _mesh, materials in snapshots for material in materials if material is not None},
        key=lambda material: material.name.lower(),
    )
    return {
        material: create_flat_id_material(f"__SPRITE_ID_{index}__", palette[index % len(palette)])
        for index, material in enumerate(originals)
    }


def replace_mesh_material_map(snapshots, material_map):
    fallback = next(iter(material_map.values()), None)
    for mesh, materials in snapshots:
        mesh.materials.clear()
        for material in materials:
            replacement = material_map.get(material, fallback)
            if replacement:
                mesh.materials.append(replacement)


def apply_animation_framing(camera, base_ortho_scale, settings, size):
    scale = max(float(settings.get("scale", 1.0)), 0.05)
    offset_x = float(settings.get("dx", 0.0))
    offset_y = float(settings.get("dy", 0.0))
    camera.data.ortho_scale = base_ortho_scale / scale
    camera.data.shift_x = -offset_x / max(float(size), 1.0)
    camera.data.shift_y = offset_y / max(float(size), 1.0)


def create_camera_and_lights(center, extent, view_axis, up_axis, padding, key_energy, fill_energy):
    if view_axis[-1] == up_axis:
        raise RuntimeError("View axis and up axis cannot use the same coordinate")
    distance = max(extent.length * 2.5, 6.0)
    bpy.ops.object.camera_add(location=camera_location(center, distance, view_axis))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    vertical_extent = getattr(extent, up_axis)
    camera.data.ortho_scale = max(vertical_extent * 2.0 * padding, 0.1)
    look_at(camera, center)
    bpy.context.scene.camera = camera

    bpy.ops.object.light_add(type="AREA", location=camera_location(center, distance * 0.45, view_axis) + Vector((0.0, 0.0, extent.z)))
    key_light = bpy.context.object
    key_light.data.energy = key_energy
    key_light.data.shape = "DISK"
    key_light.data.size = 5.0
    look_at(key_light, center)

    bpy.ops.object.light_add(type="AREA", location=camera_location(center, -distance * 0.3, view_axis) + Vector((0.0, 0.0, extent.z * 0.4)))
    fill_light = bpy.context.object
    fill_light.data.energy = fill_energy
    fill_light.data.size = 4.0
    look_at(fill_light, center)
    return camera


def safe_name(value):
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_")
    return cleaned or "animation"


def main():
    args = parse_args()
    source_path = Path(args.source).resolve()
    output_path = Path(args.output).resolve()
    if not source_path.exists():
        raise RuntimeError(f"Source does not exist: {source_path}")

    clear_scene()
    import_source(source_path)
    armatures = get_armatures()
    actions = get_actions()
    if args.list_actions:
        print_actions(actions)
    if args.list_materials:
        print_materials()
    if args.list_actions or args.list_materials:
        return
    if not armatures:
        raise RuntimeError("No armature found in source")
    if not actions:
        raise RuntimeError("No animation actions found in source")

    requested_names = [name.strip() for name in args.animations.split(",") if name.strip()]
    selected_actions = select_actions(actions, requested_names)
    animation_fps = parse_animation_fps(args.animation_fps)
    passes = [value.strip().lower() for value in args.passes.split(",") if value.strip()]
    invalid_passes = [value for value in passes if value not in ("color", "normal", "material_id")]
    if invalid_passes:
        raise RuntimeError(f"Unsupported passes: {', '.join(invalid_passes)}")
    material_colors = json.loads(args.material_colors)
    animation_settings = json.loads(args.animation_settings)
    source_fps = float(bpy.context.scene.render.fps) / max(float(bpy.context.scene.render.fps_base), 0.0001)
    mesh_objects = visible_mesh_objects(armatures)
    action_frames = {}
    overall_minimum = Vector((math.inf, math.inf, math.inf))
    overall_maximum = Vector((-math.inf, -math.inf, -math.inf))

    for action in selected_actions:
        target_fps = animation_fps.get(action.name.casefold(), args.fps)
        frames = [int(round(action.frame_range[0]))] if args.single_frame else sample_frames(action, source_fps, target_fps)
        action_frames[action.name] = frames
        minimum, maximum = combined_bounds(armatures, action, frames, mesh_objects)
        overall_minimum.x = min(overall_minimum.x, minimum.x)
        overall_minimum.y = min(overall_minimum.y, minimum.y)
        overall_minimum.z = min(overall_minimum.z, minimum.z)
        overall_maximum.x = max(overall_maximum.x, maximum.x)
        overall_maximum.y = max(overall_maximum.y, maximum.y)
        overall_maximum.z = max(overall_maximum.z, maximum.z)

    center = (overall_minimum + overall_maximum) * 0.5
    extent = (overall_maximum - overall_minimum) * 0.5
    configure_render(args.size, args.exposure)
    camera = create_camera_and_lights(center, extent, args.view_axis, args.up_axis, args.padding, args.key_light, args.fill_light)
    base_ortho_scale = camera.data.ortho_scale
    apply_flat_materials(material_colors)
    normal_material = create_normal_material()
    material_snapshots = capture_mesh_materials(mesh_objects)
    material_id_map = create_material_id_map(material_snapshots)
    output_path.mkdir(parents=True, exist_ok=True)

    manifest = {
        "source": str(source_path),
        "size": args.size,
        "fps": args.fps,
        "view_axis": args.view_axis,
        "up_axis": args.up_axis,
        "key_light": args.key_light,
        "fill_light": args.fill_light,
        "exposure": args.exposure,
        "animations": {},
        "passes": passes,
        "material_colors": material_colors,
        "animation_settings": animation_settings,
        "material_ids": {
            material.name: color_to_hex(id_material.node_tree.nodes.get("Emission").inputs["Color"].default_value)
            for material, id_material in material_id_map.items()
        },
    }
    scene = bpy.context.scene
    for action in selected_actions:
        animation_name = safe_name(action.name)
        target_fps = animation_fps.get(action.name.casefold(), args.fps)
        frame_entries = [{"index": output_index, "source_frame": source_frame} for output_index, source_frame in enumerate(action_frames[action.name])]
        manifest["animations"][animation_name] = {
            "source_action": action.name,
            "fps": target_fps,
            "frames": frame_entries,
            "framing": animation_settings.get(action.name, {"dx": 0, "dy": 0, "scale": 1}),
        }

    for pass_name in passes:
        if pass_name == "normal":
            replace_mesh_materials(material_snapshots, normal_material)
            scene.view_settings.view_transform = "Raw"
        elif pass_name == "material_id":
            replace_mesh_material_map(material_snapshots, material_id_map)
            scene.view_settings.view_transform = "Raw"
        else:
            restore_mesh_materials(material_snapshots)
            scene.view_settings.view_transform = "Standard"
        for action in selected_actions:
            assign_action(armatures, action)
            animation_name = safe_name(action.name)
            apply_animation_framing(
                camera,
                base_ortho_scale,
                animation_settings.get(action.name, {}),
                args.size,
            )
            frame_entries = manifest["animations"][animation_name]["frames"]
            animation_dir = output_path / pass_name / animation_name
            animation_dir.mkdir(parents=True, exist_ok=True)
            for frame_entry in frame_entries:
                scene.frame_set(frame_entry["source_frame"])
                scene.render.filepath = str(animation_dir / f"{animation_name}_{frame_entry['index']:04d}.png")
                bpy.ops.render.render(write_still=True)
    restore_mesh_materials(material_snapshots)

    with (output_path / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    print(f"SPRITE_PIPELINE_DONE\t{output_path}")


if __name__ == "__main__":
    main()
