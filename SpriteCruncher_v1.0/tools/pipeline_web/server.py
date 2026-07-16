import argparse
import json
import mimetypes
import re
import shutil
import subprocess
import threading
import time
import uuid
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = Path(__file__).resolve().parent / "web"
CONFIG_PATH = Path(__file__).resolve().parent / "pipeline_config.json"
RENDER_SCRIPT = PROJECT_ROOT / "tools" / "blender" / "render_sprite_frames.py"
PACK_SCRIPT = "res://tools/sprites/pack_sprite_sheet.gd"
DEFAULT_CONFIG = {
    "project_name": "横版体素角色",
    "source": "assets/blender/character/character.glb",
    "output_name": "player",
    "blender_executable": "D:/Program Files/Blender Foundation/Blender 4.5/blender.exe",
    "godot_executable": "C:/Users/Haynes/Desktop/Godot_v4.6.3-stable_win64.exe",
    "size": 150,
    "fps": 12,
    "view_axis": "+x",
    "up_axis": "z",
    "padding": 1.18,
    "columns": 8,
    "key_light": 120,
    "fill_light": 35,
    "exposure": -0.5,
    "animation_fps": {},
    "animation_settings": {},
    "material_overrides": {},
}
JOBS = {}
JOBS_LOCK = threading.Lock()


def load_config():
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {**DEFAULT_CONFIG, **data}


def save_config(config):
    normalized = {**DEFAULT_CONFIG, **config}
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, ensure_ascii=False, indent=2)


def project_path(relative_path):
    path = (PROJECT_ROOT / str(relative_path)).resolve()
    if PROJECT_ROOT != path and PROJECT_ROOT not in path.parents:
        raise ValueError("Path must stay inside the project")
    return path


def source_path(value):
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def safe_output_name(value):
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value).strip()).strip("_")
    if not cleaned:
        raise ValueError("Output name is empty")
    return cleaned


def safe_animation_name(value):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value).strip()).strip("_") or "animation"


def validate_config(config):
    source = source_path(config["source"])
    if not source.exists() or not source.is_file() or source.suffix.lower() not in (".glb", ".gltf", ".fbx"):
        raise ValueError("Source must be an existing GLB, GLTF, or FBX file")
    blender = Path(config["blender_executable"])
    godot = Path(config["godot_executable"])
    if not blender.exists():
        raise ValueError("Blender executable does not exist")
    if not godot.exists():
        raise ValueError("Godot executable does not exist")
    safe_output_name(config["output_name"])
    size = int(config["size"])
    if size < 32 or size > 1024:
        raise ValueError("Canvas size must be between 32 and 1024")
    if config["view_axis"] not in ("+x", "-x", "+y", "-y"):
        raise ValueError("Invalid view axis")
    if config.get("up_axis", "z") not in ("y", "z"):
        raise ValueError("Invalid up axis")
    if config["view_axis"][-1] == config.get("up_axis", "z"):
        raise ValueError("View axis and up axis cannot use the same coordinate")
    return source, blender, godot


def inspect_source(config):
    source, blender, _godot = validate_config(config)
    output_root = project_path(f"outputs/sprites/{safe_output_name(config['output_name'])}")
    command = [
        str(blender),
        "--background",
        "--factory-startup",
        "--python",
        str(RENDER_SCRIPT),
        "--",
        "--source",
        str(source),
        "--output",
        str(output_root),
        "--list-actions",
        "--list-materials",
    ]
    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stdout + "\n" + result.stderr)
    actions = []
    materials = []
    section = ""
    for line in result.stdout.splitlines():
        if line.strip() == "SPRITE_PIPELINE_ACTIONS":
            section = "actions"
            continue
        if line.strip() == "SPRITE_PIPELINE_MATERIALS":
            section = "materials"
            continue
        if "\t" not in line:
            continue
        parts = line.split("\t")
        if section == "actions" and len(parts) == 3:
            actions.append({"name": parts[0], "start": float(parts[1]), "end": float(parts[2])})
        elif section == "materials" and len(parts) >= 5:
            materials.append({
                "name": parts[0],
                "color": parts[1],
                "polygon_count": int(parts[2]),
                "object_count": int(parts[3]),
                "texture": parts[4],
                "used": int(parts[2]) > 0,
            })
    return {"actions": actions, "materials": materials}


def create_job(config, animations):
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "status": "queued",
        "stage": "等待构建",
        "logs": [],
        "created_at": time.time(),
        "artifacts": [],
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    threading.Thread(target=run_build_job, args=(job_id, config, animations), daemon=True).start()
    return job_id


def create_preview_job(config, animation):
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "status": "queued",
        "stage": "等待单帧预览",
        "logs": [],
        "created_at": time.time(),
        "preview": None,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    threading.Thread(target=run_preview_job, args=(job_id, config, animation), daemon=True).start()
    return job_id


def update_job(job_id, **values):
    with JOBS_LOCK:
        JOBS[job_id].update(values)


def append_log(job_id, line):
    with JOBS_LOCK:
        logs = JOBS[job_id]["logs"]
        logs.append(line.rstrip())
        if len(logs) > 600:
            del logs[:100]


def enabled_material_styles(config):
    return {
        name: {
            "mode": values.get("mode", "gradient"),
            "color": values.get("color", "#ffffff"),
            "shadow": values.get("shadow", "#18131f"),
            "mid": values.get("mid", values.get("color", "#a85b58")),
            "highlight": values.get("highlight", "#ffe0b8"),
        }
        for name, values in config.get("material_overrides", {}).items()
        if values.get("enabled", False)
    }


def run_process(job_id, command):
    append_log(job_id, "> " + " ".join(f'"{part}"' if " " in part else part for part in command))
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    for line in process.stdout:
        append_log(job_id, line)
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"Command failed with exit code {return_code}")


def run_build_job(job_id, config, animations):
    try:
        source, blender, godot = validate_config(config)
        output_name = safe_output_name(config["output_name"])
        frame_root = project_path(f"outputs/sprites/{output_name}")
        sheet_root = project_path(f"assets/sprites/{output_name}")
        if frame_root.exists():
            shutil.rmtree(frame_root)
        if sheet_root.exists():
            shutil.rmtree(sheet_root)
        frame_root.mkdir(parents=True, exist_ok=True)
        sheet_root.mkdir(parents=True, exist_ok=True)

        selected_names = [item["name"] for item in animations if item.get("enabled", True)]
        if not selected_names:
            raise ValueError("Select at least one animation")
        animation_fps = ",".join(f"{item['name']}={float(item.get('fps', config['fps']))}" for item in animations if item.get("enabled", True))
        material_colors = enabled_material_styles(config)

        update_job(job_id, status="running", stage="Blender 渲染序列帧")
        render_command = [
            str(blender),
            "--background",
            "--factory-startup",
            "--python",
            str(RENDER_SCRIPT),
            "--",
            "--source",
            str(source),
            "--output",
            str(frame_root),
            "--animations",
            ",".join(selected_names),
            "--animation-fps",
            animation_fps,
            "--animation-settings",
            json.dumps(config.get("animation_settings", {}), ensure_ascii=False),
            "--size",
            str(int(config["size"])),
            "--fps",
            str(float(config["fps"])),
            "--view-axis",
            str(config["view_axis"]),
            "--up-axis",
            str(config.get("up_axis", "z")),
            "--padding",
            str(float(config["padding"])),
            "--key-light",
            str(float(config["key_light"])),
            "--fill-light",
            str(float(config["fill_light"])),
            "--exposure",
            str(float(config["exposure"])),
            "--passes",
            "color,normal,material_id",
            "--material-colors",
            json.dumps(material_colors, ensure_ascii=False),
        ]
        run_process(job_id, render_command)

        for pass_name in ("color", "normal", "material_id"):
            update_job(job_id, stage=f"Godot 打包 {pass_name} SpriteSheet")
            pack_command = [
                str(godot),
                "--headless",
                "--path",
                str(PROJECT_ROOT),
                "--script",
                PACK_SCRIPT,
                "--",
                "--input",
                str(frame_root / pass_name),
                "--output",
                str(sheet_root / pass_name),
                "--columns",
                str(int(config["columns"])),
            ]
            run_process(job_id, pack_command)

        artifacts = list_artifacts(output_name)
        update_job(job_id, status="completed", stage="构建完成", artifacts=artifacts)
    except Exception as error:
        append_log(job_id, f"ERROR: {error}")
        update_job(job_id, status="failed", stage="构建失败")


def run_preview_job(job_id, config, animation):
    try:
        source, blender, _godot = validate_config(config)
        output_name = safe_output_name(config["output_name"])
        action_name = str(animation.get("name", "")).strip()
        if not action_name:
            raise ValueError("Select an animation to preview")
        animation_name = safe_animation_name(action_name)
        preview_root = project_path(f"outputs/previews/{output_name}")
        if preview_root.exists():
            shutil.rmtree(preview_root)
        preview_root.mkdir(parents=True, exist_ok=True)
        material_colors = enabled_material_styles(config)

        update_job(job_id, status="running", stage="Blender 渲染单帧预览")
        command = [
            str(blender),
            "--background",
            "--factory-startup",
            "--python",
            str(RENDER_SCRIPT),
            "--",
            "--source",
            str(source),
            "--output",
            str(preview_root),
            "--animations",
            action_name,
            "--animation-settings",
            json.dumps(config.get("animation_settings", {}), ensure_ascii=False),
            "--size",
            str(int(config["size"])),
            "--fps",
            str(float(config["fps"])),
            "--view-axis",
            str(config["view_axis"]),
            "--up-axis",
            str(config.get("up_axis", "z")),
            "--padding",
            str(float(config["padding"])),
            "--key-light",
            str(float(config["key_light"])),
            "--fill-light",
            str(float(config["fill_light"])),
            "--exposure",
            str(float(config["exposure"])),
            "--passes",
            "color,normal,material_id",
            "--material-colors",
            json.dumps(material_colors, ensure_ascii=False),
            "--single-frame",
        ]
        run_process(job_id, command)
        color_path = preview_root / "color" / animation_name / f"{animation_name}_0000.png"
        normal_path = preview_root / "normal" / animation_name / f"{animation_name}_0000.png"
        material_id_path = preview_root / "material_id" / animation_name / f"{animation_name}_0000.png"
        if not color_path.exists() or not normal_path.exists() or not material_id_path.exists():
            raise RuntimeError("Preview images were not generated")
        preview = {
            "animation": animation_name,
            "source_action": action_name,
            "color_url": "/files/" + color_path.relative_to(PROJECT_ROOT).as_posix(),
            "normal_url": "/files/" + normal_path.relative_to(PROJECT_ROOT).as_posix(),
            "material_id_url": "/files/" + material_id_path.relative_to(PROJECT_ROOT).as_posix(),
            "modified_at": max(color_path.stat().st_mtime, normal_path.stat().st_mtime),
            "size": int(config["size"]),
            "framing": config.get("animation_settings", {}).get(action_name, {"dx": 0, "dy": 0, "scale": 1}),
            "is_preview": True,
        }
        update_job(job_id, status="completed", stage="单帧预览完成", preview=preview)
    except Exception as error:
        append_log(job_id, f"ERROR: {error}")
        update_job(job_id, status="failed", stage="预览失败")


def list_artifacts(output_name):
    safe_name = safe_output_name(output_name)
    sheet_root = project_path(f"assets/sprites/{safe_name}")
    color_root = sheet_root / "color"
    normal_root = sheet_root / "normal"
    material_id_root = sheet_root / "material_id"
    manifest_path = project_path(f"outputs/sprites/{safe_name}/manifest.json")
    manifest = {}
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    if not color_root.exists():
        return []
    artifacts = []
    for image_path in sorted(color_root.glob("*.png")):
        metadata_path = image_path.with_suffix(".json")
        normal_path = normal_root / image_path.name
        material_id_path = material_id_root / image_path.name
        artifacts.append({
            "animation": image_path.stem,
            "color_url": "/files/" + image_path.relative_to(PROJECT_ROOT).as_posix(),
            "normal_url": "/files/" + normal_path.relative_to(PROJECT_ROOT).as_posix() if normal_path.exists() else "",
            "material_id_url": "/files/" + material_id_path.relative_to(PROJECT_ROOT).as_posix() if material_id_path.exists() else "",
            "metadata_url": "/files/" + metadata_path.relative_to(PROJECT_ROOT).as_posix() if metadata_path.exists() else "",
            "modified_at": image_path.stat().st_mtime,
            "framing": manifest.get("animations", {}).get(image_path.stem, {}).get("framing", {"dx": 0, "dy": 0, "scale": 1}),
        })
    return artifacts


class PipelineHandler(SimpleHTTPRequestHandler):
    def log_message(self, format_string, *args):
        print("PIPELINE_WEB", format_string % args)

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 2_000_000:
            raise ValueError("Request is too large")
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            self.send_json(load_config())
            return
        if parsed.path == "/api/artifacts":
            config = load_config()
            self.send_json({"artifacts": list_artifacts(config["output_name"])})
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                payload = dict(job) if job else None
            self.send_json(payload or {"error": "Job not found"}, 200 if job else 404)
            return
        if parsed.path.startswith("/files/"):
            self.serve_project_file(unquote(parsed.path[len("/files/") :]))
            return
        self.serve_static(parsed.path)

    def do_POST(self):
        try:
            payload = self.read_json()
            if self.path == "/api/config":
                config = {**load_config(), **payload}
                validate_config(config)
                save_config(config)
                self.send_json(config)
                return
            if self.path == "/api/actions":
                config = {**load_config(), **payload.get("config", {})}
                self.send_json(inspect_source(config))
                return
            if self.path == "/api/build":
                config = {**load_config(), **payload.get("config", {})}
                validate_config(config)
                save_config(config)
                job_id = create_job(config, payload.get("animations", []))
                self.send_json({"job_id": job_id}, 202)
                return
            if self.path == "/api/preview":
                config = {**load_config(), **payload.get("config", {})}
                validate_config(config)
                save_config(config)
                job_id = create_preview_job(config, payload.get("animation", {}))
                self.send_json({"job_id": job_id}, 202)
                return
            self.send_json({"error": "Not found"}, 404)
        except Exception as error:
            self.send_json({"error": str(error)}, 400)

    def serve_project_file(self, relative_path):
        try:
            file_path = project_path(relative_path)
            allowed_roots = [project_path("assets"), project_path("outputs")]
            if not any(root == file_path or root in file_path.parents for root in allowed_roots):
                raise ValueError("File is outside preview directories")
            self.send_file(file_path)
        except Exception as error:
            self.send_json({"error": str(error)}, 404)

    def serve_static(self, request_path):
        relative = "index.html" if request_path in ("", "/") else request_path.lstrip("/")
        file_path = (STATIC_ROOT / relative).resolve()
        if STATIC_ROOT != file_path and STATIC_ROOT not in file_path.parents:
            self.send_json({"error": "Invalid static path"}, 404)
            return
        self.send_file(file_path)

    def send_file(self, file_path):
        if not file_path.exists() or not file_path.is_file():
            self.send_json({"error": "File not found"}, 404)
            return
        content = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), PipelineHandler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"SPRITE_CRUNCHER_URL={url}")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
