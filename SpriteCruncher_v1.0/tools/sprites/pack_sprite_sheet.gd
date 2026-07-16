extends SceneTree


func _init() -> void:
	var options := _parse_options(OS.get_cmdline_user_args())
	if not options.has("input") or not options.has("output"):
		push_error("Usage: --input <frame_root> --output <sheet_root> [--columns 8]")
		quit(1)
		return

	var input_root := ProjectSettings.globalize_path(str(options["input"]))
	var output_root := ProjectSettings.globalize_path(str(options["output"]))
	var columns := maxi(int(options.get("columns", "8")), 1)
	DirAccess.make_dir_recursive_absolute(output_root)

	var packed_count := 0
	for directory_name in DirAccess.get_directories_at(input_root):
		var animation_directory := input_root.path_join(directory_name)
		var frame_paths := _get_png_paths(animation_directory)
		if frame_paths.is_empty():
			continue
		_pack_animation(directory_name, frame_paths, output_root, columns)
		packed_count += 1

	print("SPRITE_SHEETS_PACKED: %d" % packed_count)
	quit(0)


func _parse_options(arguments: PackedStringArray) -> Dictionary:
	var options := {}
	var index := 0
	while index < arguments.size():
		var argument := arguments[index]
		if argument.begins_with("--") and index + 1 < arguments.size():
			options[argument.trim_prefix("--")] = arguments[index + 1]
			index += 2
		else:
			index += 1
	return options


func _get_png_paths(directory_path: String) -> PackedStringArray:
	var paths := PackedStringArray()
	for file_name in DirAccess.get_files_at(directory_path):
		if file_name.get_extension().to_lower() == "png":
			paths.append(directory_path.path_join(file_name))
	paths.sort()
	return paths


func _pack_animation(animation_name: String, frame_paths: PackedStringArray, output_root: String, columns: int) -> void:
	var first_image := Image.load_from_file(frame_paths[0])
	if first_image == null or first_image.is_empty():
		push_error("Cannot load frame: %s" % frame_paths[0])
		return

	var frame_width := first_image.get_width()
	var frame_height := first_image.get_height()
	var rows := ceili(float(frame_paths.size()) / float(columns))
	var atlas := Image.create_empty(frame_width * columns, frame_height * rows, false, Image.FORMAT_RGBA8)
	atlas.fill(Color.TRANSPARENT)
	var frame_data := []

	for frame_index in frame_paths.size():
		var frame_image := Image.load_from_file(frame_paths[frame_index])
		if frame_image == null or frame_image.is_empty():
			push_error("Cannot load frame: %s" % frame_paths[frame_index])
			continue
		if frame_image.get_size() != Vector2i(frame_width, frame_height):
			push_error("Frame size mismatch: %s" % frame_paths[frame_index])
			continue
		frame_image.convert(Image.FORMAT_RGBA8)
		var column := frame_index % columns
		var row := frame_index / columns
		var destination := Vector2i(column * frame_width, row * frame_height)
		atlas.blit_rect(frame_image, Rect2i(Vector2i.ZERO, frame_image.get_size()), destination)
		frame_data.append({
			"index": frame_index,
			"x": destination.x,
			"y": destination.y,
			"width": frame_width,
			"height": frame_height,
			"source": frame_paths[frame_index].get_file(),
		})

	var sheet_path := output_root.path_join("%s.png" % animation_name)
	var error := atlas.save_png(sheet_path)
	if error != OK:
		push_error("Cannot save sprite sheet: %s" % sheet_path)
		return

	var metadata := {
		"animation": animation_name,
		"frame_width": frame_width,
		"frame_height": frame_height,
		"frame_count": frame_paths.size(),
		"columns": columns,
		"rows": rows,
		"frames": frame_data,
	}
	var metadata_file := FileAccess.open(output_root.path_join("%s.json" % animation_name), FileAccess.WRITE)
	metadata_file.store_string(JSON.stringify(metadata, "\t"))
	print("PACKED: %s" % sheet_path)
