中文：

3D 转 2D 角色管线
这是一个本地工具：Blender 负责读取角色、骨骼和动画，工具自动输出 2D 的 Color SpriteSheet 与 Normal SpriteSheet。Color 只保存角色色彩，Normal 交给 Godot 在游戏运行时计算光影。

第一次使用
双击 启动管线.bat。
浏览器会打开 http://127.0.0.1:8877。
在“源 GLB / FBX”中填写角色文件的完整路径。
点击“扫描动作”。
勾选需要导出的动画，并给每个动画设置 FPS。
需要换色时，勾选材质区块并设置暗部、主色和高光；工具会根据原纹理明度进行渐变映射。不勾选就保留 Blender 原材质或纹理。
点击“构建选中动画”。
只想检查构图或材质时，可以点击“单帧预览”。它只渲染当前动作的第一帧 Color、Normal 与 Material ID，不打包 SpriteSheet，也不会覆盖已经构建好的正式动画图集。确认满意后，再点击“构建选中动画”。

网页中的三种预览：

Color：最终基础色，不包含灯光和阴影。
Normal：表面方向数据，不是给人直接看的颜色图。
Material ID：每个有效材质使用唯一纯色显示，用于检查 Blender 材质分区。
Composite：浏览器用 Color + Normal 临时合成的光照效果。鼠标在预览区移动可以改变光源方向。
渐变换色不会用纯色盖住纹理：黑色和深灰映射到“暗”，中灰映射到“中”，浅灰和白色映射到“亮”。如果一个材质包含整个人物，整个人物会共用一条渐变；要让皮肤、头发和衣服使用不同渐变，需要在 Blender 中拆成不同材质。

动画构图
扫描后点击左侧动作名称，右侧“当前动作构图”会切换到该动作。每个动作分别保存：

X 偏移：以输出像素为单位左右移动角色。
Y 偏移：以输出像素为单位上下移动角色。
角色缩放：1 为默认，1.2 表示放大 20%。
修改 X 偏移、Y 偏移 或 角色缩放 时，中央画布会立即更新，不需要重新构建动画。扫描模型后会自动生成当前动作的单帧预览；修改材质颜色后也会自动刷新单帧。

当前默认画布为 150×150。待机、跑步、攻击可以使用不同构图，但 Color、Normal、Material ID 始终保持同样的画布和偏移。

材质诊断
材质卡片会显示可见网格使用面数、对象数和连接的纹理名称。灰暗并标记“未被可见网格使用”的材质不会影响当前角色。拆分 Blender 材质后重新扫描，可通过 Material ID 模式检查 skin、hair、clothes 等区域是否分配正确。

Composite 只用于判断效果，不会把光影写进 Color 图。

Blender 角色准备规则
一个角色导出为一个 .glb、.gltf 或 .fbx。
骨骼动画必须保存为 Blender Action，并使用清楚的名字，例如 idle_loop、run_loop、attack_01。
需要在网页里独立换色的区域，要在 Blender 中使用不同材质槽并正确命名，例如 skin、hair、coat。
Color 图要保持平面色；不要提前烘焙固定方向的灯光和阴影。
建模、骨骼权重和动作质量仍由 Blender 负责，本工具只自动完成扫描、逐帧渲染、法线输出和图集打包。
更换角色
更换“源 GLB / FBX”的路径，并修改“输出标识”，然后重新扫描和构建。不同角色使用不同输出标识，例如：

player
zombie_small
boss_knight
这样旧角色的图集不会和新角色混在一起。

输出位置
逐帧中间文件：

outputs/sprites/<角色>/color/<动画>/
outputs/sprites/<角色>/normal/<动画>/
Godot 使用的最终图集：

assets/sprites/<角色>/color/<动画>.png
assets/sprites/<角色>/color/<动画>.json
assets/sprites/<角色>/normal/<动画>.png
assets/sprites/<角色>/normal/<动画>.json
Color 与 Normal 的画布尺寸、帧数和排列完全一致，可以在 Godot 中一一对应。

Godot 中怎么用
最基础的做法是让角色的 Sprite2D 使用 Color 图集，再准备同帧的 Normal 图集供 2D 法线光照材质读取。动画切换时，Color 与 Normal 必须使用相同的动画名和帧编号。

目前管线负责生成标准产物，但不会自动修改你的游戏场景，避免覆盖现有角色节点。下一步可以在游戏项目中制作一个统一的角色 Sprite Shader 和动画资源导入器。

常见问题
扫描失败：检查 Blender 路径、角色文件路径以及文件是否存在。
没有动作：确认动画已经存为 Action，而不只是时间轴上的临时关键帧。
没有材质区块：确认模型使用了材质槽，并给材质命名。
Color 泛白：检查 Blender 原纹理、材质 Base Color 和颜色管理，不要把灯光效果画进基础色。
Normal 看起来是彩色：这是正常的，RGB 分别编码表面三个方向。
构建后网页没变化：切换动画标签，或刷新页面后重新加载产物。







English： Voxel Sprite Cruncher A local tool: Blender reads your character, skeleton, and animations, and the tool outputs 2D Color SpriteSheets and Normal SpriteSheets. Color stores only the character's flat color; Normal maps are handed to Godot for runtime lighting.

Quick Start Double-click launch.bat. Your browser opens http://127.0.0.1:8877. Enter the full path to your GLB / FBX file under "Source GLB / FBX". Click Scan Actions. Check the animations you want to export, and set an FPS for each. To recolor, check a material slot and set its shadow, mid, and highlight colors. The tool remaps based on the original texture's brightness. Leave unchecked to keep the Blender material as-is. Click Build Selected. To check framing or materials without generating a full SpriteSheet, click Preview Single Frame. It renders only the first frame of the current action (Color, Normal, and Material ID) without overwriting previously built sprites. Once satisfied, click Build Selected.

Four preview modes in the browser:

Color — Final flat color, no lights or shadows. Normal — Surface direction data; not meant as a visual image. Material ID — Each material shown as a unique solid color for diagnosing Blender material assignment. Composite — Browser-composited toon lighting using Color + Normal. Move your mouse over the preview to change the light direction. Gradient remapping does not replace your texture with solid colors: black and dark gray map to "shadow", mid gray to "main", and light gray / white to "highlight". If a material covers the entire character, the whole character shares one gradient. To give different gradients to skin, hair, and clothing, split them into separate materials in Blender.

Animation Framing After scanning, click an action name in the left panel to display its framing controls on the right. Each action stores:

X Offset — Shift the character left or right in output pixels. Y Offset — Shift the character up or down in output pixels. Scale — 1 = default size; 1.2 = 20% larger. Changing any of these immediately updates the preview canvas — no rebuild required. After scanning, a single-frame preview is auto-generated. Changing material colors also auto-refreshes the preview.

The default canvas is 150×150. Idle, run, and attack actions can each have different framing, but Color, Normal, and Material ID always share the same canvas and offsets.

Material Diagnostics Material cards show visible mesh face count, object count, and linked texture names. Materials dimmed and marked "Not used by visible mesh" do not affect the current character. After splitting Blender materials, re-scan and use the Material ID preview to verify that skin, hair, clothes, etc. are correctly assigned.

Composite preview is for evaluation only; it does not bake lighting into the Color map.

Blender Character Guidelines Export one character as a single .glb, .gltf, or .fbx. Skeletal animations must be saved as Blender Actions with clear names such as idle_loop, run_loop, attack_01. Areas you want to recolor independently in the tool must use separate material slots in Blender with meaningful names like skin, hair, coat. Keep Color maps flat; do not pre-bake directional lights or shadows. Modeling, skinning, and animation quality remain the responsibility of Blender. This tool only automates scanning, frame rendering, normal output, and atlas packing. Switching Characters Change the "Source GLB / FBX" path and the "Output ID", then re-scan and rebuild. Use different output IDs for different characters, such as:

player zombie_small boss_knight This keeps old character atlases separate from new ones.

Output Locations Intermediate per-frame files:

outputs/sprites//color// outputs/sprites//normal// Final SpriteSheets for Godot:

assets/sprites//color/.png assets/sprites//color/.json assets/sprites//normal/.png assets/sprites//normal/.json Color and Normal atlases have identical canvas sizes, frame counts, and layout — they map 1:1 in Godot.

Usage in Godot The simplest approach: give your Sprite2D the Color atlas as its texture, and supply the corresponding Normal atlas to a 2D normal-lit shader material. When switching animations, Color and Normal must use the same animation name and frame index.

The pipeline generates standard assets but does not modify your game scene, avoiding overwrites to existing character nodes. The next step is building a unified character sprite shader and animation resource importer in your game project.

FAQ Scan fails — Check your Blender path, character file path, and that the file exists. No actions found — Make sure animations are saved as Actions, not just temporary keyframes on the timeline. No material slots — Confirm the model uses material slots in Blender and that each is named. Color looks washed out — Check your Blender texture, material Base Color, and color management. Do not bake lighting into base color. Normal looks colorful — This is normal. RGB channels encode three surface directions. Nothing changes after build — Switch to a different animation tab, or refresh the page and reload the assets.
