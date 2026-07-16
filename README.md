# Voxel Sprite Cruncher / 体素精灵转换器

[English](#english) | [中文](#中文)

Blender 3D models → pixel SpriteSheet. One click. Free & open source.

---

## English

A local tool that scans your 3D character's skeleton and animations, renders every frame, and outputs Color + Normal SpriteSheets ready for Godot. Inspired by the Dead Cells 3D-to-2D animation pipeline.

### Quick Start

1. Double-click `launch.bat`
2. Open `http://127.0.0.1:8877`
3. Enter the full path to your GLB / FBX file
4. Click **Scan Actions**
5. Check the animations you want, set FPS per action
6. Click **Build Selected**

### Preview Modes

- **Color** — Flat final color, no lights or shadows
- **Normal** — Surface direction data for runtime lighting
- **Material ID** — Solid colors per material (diagnose Blender assignments)
- **Composite** — Real-time toon lighting preview (move mouse to change light)

### Output

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

### Requirements

- Blender 4.0+
- Python 3.10+
- Godot 4.x (for SpriteSheet packing)

### License

MIT

---

## 中文

一个本地工具：Blender 读取角色、骨骼和动画，逐帧渲染，输出 Color + Normal SpriteSheet，Godot 直接可用。参考《死亡细胞》的 3D 转 2D 动画管线。

### 快速开始

1. 双击 `launch.bat`
2. 浏览器打开 `http://127.0.0.1:8877`
3. 填写 GLB / FBX 文件的完整路径
4. 点击**扫描动作**
5. 勾选需要导出的动画，设置 FPS
6. 点击**构建选中动画**

### 预览模式

- **Color** — 最终平面色，不含灯光阴影
- **Normal** — 表面方向数据，用于运行时计算光照
- **Material ID** — 每种材质显示为纯色，用于检查 Blender 材质分区
- **Composite** — 浏览器端实时合成的卡通光照效果（鼠标移动可改变光源方向）

### 输出目录

```
assets/sprites/<角色>/
├── color/
│   ├── idle_loop.png      # SpriteSheet 图集
│   ├── idle_loop.json     # 帧元数据
│   └── ...
├── normal/
│   ├── idle_loop.png
│   └── ...
```

### 环境要求

- Blender 4.0+
- Python 3.10+
- Godot 4.x（用于打包 SpriteSheet）

### 许可证

MIT

---

## Support / 支持

If this tool helps you, consider supporting:

| 支付宝 | 微信 | itch.io |
|--------|------|---------|
| ![支付宝](alipay.png) | ![微信](wechat.png) | [Buy me a coffee](https://yumi-233.itch.io/voxel-sprite-cruncher-3d-to-pixel-spritesheet) |
