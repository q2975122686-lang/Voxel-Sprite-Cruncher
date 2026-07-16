# Voxel Sprite Cruncher

**Blender 3D models → pixel SpriteSheet. One click.**

A local tool that scans your character's skeleton and animations, renders every frame, and outputs Color + Normal SpriteSheets ready for Godot.

Inspired by the Dead Cells 3D-to-2D animation pipeline.

## Quick Start

1. Double-click `launch.bat`
2. Open `http://127.0.0.1:8877`
3. Enter the full path to your GLB / FBX file
4. Click **Scan Actions**
5. Check the animations you want, set FPS per action
6. Click **Build Selected**

## Preview Modes

- **Color** — Flat final color, no lights or shadows
- **Normal** — Surface direction data for runtime lighting
- **Material ID** — Solid colors per material (diagnose Blender assignments)
- **Composite** — Real-time toon lighting preview (move mouse to change light)

## Output

```
assets/sprites/<character>/
├── color/
│   ├── idle_loop.png      # SpriteSheet atlas
│   ├── idle_loop.json     # Frame metadata
│   └── ...
├── normal/
│   ├── idle_loop.png
│   └── ...
```

Color and Normal atlases have identical sizes, counts, and layout — map 1:1 in Godot.

## Requirements

- Blender 4.0+
- Python 3.10+
- Godot 4.x (for SpriteSheet packing)

## License

MIT

## Support

Find this useful? Consider supporting development:

https://yumi-233.itch.io/voxel-sprite-cruncher-3d-to-pixel-spritesheet
