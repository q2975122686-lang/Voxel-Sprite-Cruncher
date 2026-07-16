const state = {
  config: null,
  actions: [],
  materials: [],
  artifacts: [],
  currentArtifact: null,
  previewImage: null,
  previewNormalImage: null,
  previewMaterialIdImage: null,
  previewMetadata: null,
  previewMode: "composite",
  previewLight: { x: -0.45, y: -0.35, z: 0.82 },
  previewFrame: 0,
  previewPlaying: true,
  previewLastTime: 0,
  activeActionName: null,
  jobTimer: null,
  previewTimer: null,
  previewQueued: false,
};

const elements = {
  projectName: document.querySelector("#projectName"),
  sourcePath: document.querySelector("#sourcePath"),
  outputName: document.querySelector("#outputName"),
  blenderPath: document.querySelector("#blenderPath"),
  godotPath: document.querySelector("#godotPath"),
  canvasSize: document.querySelector("#canvasSize"),
  defaultFps: document.querySelector("#defaultFps"),
  viewAxis: document.querySelector("#viewAxis"),
  padding: document.querySelector("#padding"),
  columns: document.querySelector("#columns"),
  framingActionName: document.querySelector("#framingActionName"),
  frameOffsetX: document.querySelector("#frameOffsetX"),
  frameOffsetY: document.querySelector("#frameOffsetY"),
  frameScale: document.querySelector("#frameScale"),
  actionList: document.querySelector("#actionList"),
  materialList: document.querySelector("#materialList"),
  actionCount: document.querySelector("#actionCount"),
  scanButton: document.querySelector("#scanButton"),
  previewButton: document.querySelector("#previewButton"),
  buildButton: document.querySelector("#buildButton"),
  saveButton: document.querySelector("#saveButton"),
  playButton: document.querySelector("#playButton"),
  previewInfo: document.querySelector("#previewInfo"),
  previewCanvas: document.querySelector("#previewCanvas"),
  previewStage: document.querySelector(".preview-stage"),
  previewModes: document.querySelector("#previewModes"),
  artifactTabs: document.querySelector("#artifactTabs"),
  sheetImage: document.querySelector("#sheetImage"),
  jobStage: document.querySelector("#jobStage"),
  jobState: document.querySelector("#jobState"),
  progressBar: document.querySelector("#progressBar"),
  buildLog: document.querySelector("#buildLog"),
  toast: document.querySelector("#toast"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `请求失败：${response.status}`);
  return payload;
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  window.setTimeout(() => elements.toast.classList.remove("show"), 2200);
}

function readConfigForm() {
  const animationFps = state.actions.length
    ? Object.fromEntries(state.actions.map((action) => [action.name, Number(action.fps)]))
    : state.config?.animation_fps || {};
  const materialOverrides = state.materials.length
    ? Object.fromEntries(
      state.materials.map((material) => [material.name, {
        enabled: material.enabled,
        mode: "gradient",
        shadow: material.shadow,
        mid: material.mid,
        highlight: material.highlight,
      }])
    )
    : state.config?.material_overrides || {};
  const animationSettings = state.actions.length
    ? Object.fromEntries(state.actions.map((action) => [action.name, action.framing]))
    : state.config?.animation_settings || {};
  return {
    ...state.config,
    project_name: elements.projectName.value.trim(),
    source: elements.sourcePath.value.trim(),
    output_name: elements.outputName.value.trim(),
    blender_executable: elements.blenderPath.value.trim(),
    godot_executable: elements.godotPath.value.trim(),
    size: Number(elements.canvasSize.value),
    fps: Number(elements.defaultFps.value),
    view_axis: elements.viewAxis.value,
    padding: Number(elements.padding.value),
    columns: Number(elements.columns.value),
    animation_fps: animationFps,
    animation_settings: animationSettings,
    material_overrides: materialOverrides,
  };
}

function writeConfigForm(config) {
  elements.projectName.value = config.project_name || "";
  elements.sourcePath.value = config.source || "";
  elements.outputName.value = config.output_name || "player";
  elements.blenderPath.value = config.blender_executable || "";
  elements.godotPath.value = config.godot_executable || "";
  elements.canvasSize.value = config.size || 150;
  elements.defaultFps.value = config.fps || 12;
  elements.viewAxis.value = config.view_axis || "+x";
  elements.padding.value = config.padding || 1.18;
  elements.columns.value = config.columns || 8;
}

async function loadConfig() {
  state.config = await api("/api/config");
  writeConfigForm(state.config);
}

function renderActions() {
  elements.actionCount.textContent = `${state.actions.length} 项`;
  if (!state.actions.length) {
    elements.actionList.innerHTML = '<div class="empty-state">没有检测到动画动作</div>';
    return;
  }
  elements.actionList.replaceChildren();
  for (const action of state.actions) {
    const item = document.createElement("div");
    item.className = "action-item";
    item.dataset.action = action.name;
    item.classList.toggle("active", action.name === state.activeActionName);

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = action.enabled;
    checkbox.addEventListener("change", () => { action.enabled = checkbox.checked; });

    const name = document.createElement("div");
    name.className = "action-name";
    const title = document.createElement("strong");
    title.textContent = action.name;
    const range = document.createElement("small");
    range.textContent = `${action.start} — ${action.end}`;
    name.append(title, range);
    name.title = "点击编辑该动作的构图";
    name.addEventListener("click", () => setActiveAction(action.name));

    const fps = document.createElement("input");
    fps.type = "number";
    fps.min = "1";
    fps.max = "60";
    fps.className = "fps-input";
    fps.value = action.fps;
    fps.title = "动画 FPS";
    fps.addEventListener("change", () => { action.fps = Math.max(1, Number(fps.value)); });

    item.append(checkbox, name, fps);
    elements.actionList.append(item);
  }
}

function setActiveAction(actionName) {
  state.activeActionName = actionName;
  for (const item of elements.actionList.querySelectorAll(".action-item")) {
    item.classList.toggle("active", item.dataset.action === actionName);
  }
  renderFramingControls();
  const artifact = state.artifacts.find((item) => item.animation === actionName);
  if (artifact && state.currentArtifact?.animation !== actionName) {
    selectArtifact(artifact).catch((error) => showToast(error.message));
  } else {
    drawPreviewFrame();
  }
}

function activeAction() {
  return state.actions.find((action) => action.name === state.activeActionName) || null;
}

function renderFramingControls() {
  const action = activeAction();
  const disabled = !action;
  elements.framingActionName.textContent = action?.name || "等待扫描";
  elements.frameOffsetX.disabled = disabled;
  elements.frameOffsetY.disabled = disabled;
  elements.frameScale.disabled = disabled;
  elements.frameOffsetX.value = action?.framing.dx ?? 0;
  elements.frameOffsetY.value = action?.framing.dy ?? 0;
  elements.frameScale.value = action?.framing.scale ?? 1;
}

function updateActiveFraming() {
  const action = activeAction();
  if (!action) return;
  action.framing = {
    dx: Number(elements.frameOffsetX.value) || 0,
    dy: Number(elements.frameOffsetY.value) || 0,
    scale: Math.max(Number(elements.frameScale.value) || 1, 0.05),
  };
  drawPreviewFrame();
}

function renderMaterials() {
  if (!state.materials.length) {
    elements.materialList.innerHTML = '<div class="empty-state">没有检测到材质区块</div>';
    return;
  }
  elements.materialList.replaceChildren();
  for (const material of state.materials) {
    const item = document.createElement("div");
    item.className = "material-item";

    const header = document.createElement("label");
    header.className = "material-header";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = material.enabled;

    const name = document.createElement("strong");
    name.textContent = material.name;
    name.title = material.name;
    header.append(checkbox, name);

    const diagnostics = document.createElement("div");
    diagnostics.className = "material-diagnostics";
    const usage = document.createElement("span");
    usage.textContent = material.used
      ? `${material.polygon_count} 面 · ${material.object_count} 对象`
      : "未被可见网格使用";
    const texture = document.createElement("span");
    texture.textContent = material.texture ? `纹理：${material.texture}` : "无纹理";
    texture.title = material.texture || "";
    diagnostics.append(usage, texture);
    item.classList.toggle("unused", !material.used);

    const gradient = document.createElement("div");
    gradient.className = "gradient-editor";
    const preview = document.createElement("div");
    preview.className = "gradient-strip";
    const controls = [
      createGradientControl(material, "shadow", "暗"),
      createGradientControl(material, "mid", "中"),
      createGradientControl(material, "highlight", "亮"),
    ];
    const updateGradient = () => {
      preview.style.background = `linear-gradient(90deg, ${material.shadow}, ${material.mid}, ${material.highlight})`;
    };
    for (const control of controls) {
      control.input.disabled = !material.enabled;
      control.input.addEventListener("input", updateGradient);
      control.input.addEventListener("change", () => schedulePreviewRender());
      gradient.append(control.label);
    }
    gradient.append(preview);
    updateGradient();

    checkbox.addEventListener("change", () => {
      material.enabled = checkbox.checked;
      item.classList.toggle("active", material.enabled);
      for (const control of controls) control.input.disabled = !material.enabled;
      schedulePreviewRender();
    });
    item.classList.toggle("active", material.enabled);
    item.append(header, diagnostics, gradient);
    elements.materialList.append(item);
  }
}

function createGradientControl(material, property, title) {
  const label = document.createElement("label");
  label.className = "gradient-color";
  const caption = document.createElement("span");
  caption.textContent = title;
  const input = document.createElement("input");
  input.type = "color";
  input.value = material[property];
  input.title = `${material.name} · ${title}部颜色`;
  input.addEventListener("input", () => { material[property] = input.value; });
  label.append(caption, input);
  return { label, input };
}

function mixHex(first, second, amount) {
  const parse = (value) => [1, 3, 5].map((index) => Number.parseInt(value.slice(index, index + 2), 16));
  const left = parse(first);
  const right = parse(second);
  const channels = left.map((value, index) => Math.round(value + (right[index] - value) * amount));
  return `#${channels.map((value) => value.toString(16).padStart(2, "0")).join("")}`;
}

async function scanActions() {
  setBusy(elements.scanButton, true, "扫描中…");
  try {
    const config = readConfigForm();
    const payload = await api("/api/actions", {
      method: "POST",
      body: JSON.stringify({ config }),
    });
    state.actions = payload.actions.map((action) => ({
      ...action,
      enabled: action.name !== "default",
      fps: config.animation_fps?.[action.name] || config.fps || 12,
      framing: {
        dx: Number(config.animation_settings?.[action.name]?.dx) || 0,
        dy: Number(config.animation_settings?.[action.name]?.dy) || 0,
        scale: Number(config.animation_settings?.[action.name]?.scale) || 1,
      },
    }));
    state.materials = payload.materials.map((material) => {
      const saved = config.material_overrides?.[material.name];
      const base = saved?.mid || saved?.color || material.color || "#cccccc";
      return {
        ...material,
        enabled: Boolean(saved?.enabled),
        shadow: saved?.shadow || mixHex(base, "#000000", 0.72),
        mid: base,
        highlight: saved?.highlight || mixHex(base, "#ffffff", 0.58),
      };
    });
    const preferredAction = state.actions.find((action) => action.name === state.currentArtifact?.animation && action.enabled)
      || state.actions.find((action) => action.enabled)
      || state.actions[0];
    state.activeActionName = preferredAction?.name || null;
    renderActions();
    renderFramingControls();
    renderMaterials();
    showToast(`读取到 ${state.actions.length} 个动作、${state.materials.length} 个材质`);
    schedulePreviewRender(0);
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(elements.scanButton, false, "扫描动作");
  }
}

function setBusy(button, busy, busyText) {
  if (!button.dataset.defaultText) button.dataset.defaultText = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? busyText : button.dataset.defaultText;
}

async function saveConfig() {
  const config = readConfigForm();
  state.config = await api("/api/config", {
    method: "POST",
    body: JSON.stringify(config),
  });
  showToast("配置已保存");
}

async function startBuild() {
  updateActiveFraming();
  const animations = state.actions.filter((action) => action.enabled);
  if (!animations.length) {
    showToast("请先扫描并选择动画");
    return;
  }
  setBusy(elements.buildButton, true, "构建中…");
  try {
    const config = readConfigForm();
    const payload = await api("/api/build", {
      method: "POST",
      body: JSON.stringify({ config, animations }),
    });
    state.config = config;
    pollJob(payload.job_id, "build");
  } catch (error) {
    setBusy(elements.buildButton, false, "构建选中动画");
    showToast(error.message);
  }
}

async function startPreview() {
  updateActiveFraming();
  const animation = state.actions.find((item) => item.enabled && item.name === state.activeActionName)
    || state.actions.find((item) => item.enabled && item.name === state.currentArtifact?.animation)
    || state.actions.find((item) => item.enabled);
  if (!animation) {
    showToast("请先扫描并选择一个动画");
    return;
  }
  setBusy(elements.previewButton, true, "预览中…");
  try {
    const config = readConfigForm();
    const payload = await api("/api/preview", {
      method: "POST",
      body: JSON.stringify({ config, animation }),
    });
    state.config = config;
    pollJob(payload.job_id, "preview");
  } catch (error) {
    setBusy(elements.previewButton, false, "单帧预览");
    showToast(error.message);
  }
}

function schedulePreviewRender(delay = 450) {
  window.clearTimeout(state.previewTimer);
  state.previewTimer = window.setTimeout(() => {
    state.previewTimer = null;
    if (elements.previewButton.disabled) {
      state.previewQueued = true;
      return;
    }
    startPreview();
  }, delay);
}

function pollJob(jobId, mode) {
  window.clearInterval(state.jobTimer);
  const update = async () => {
    try {
      const job = await api(`/api/jobs/${jobId}`);
      renderJob(job);
      if (job.status === "completed" || job.status === "failed") {
        window.clearInterval(state.jobTimer);
        state.jobTimer = null;
        if (mode === "preview") {
          setBusy(elements.previewButton, false, "单帧预览");
        } else {
          setBusy(elements.buildButton, false, "构建选中动画");
        }
        if (job.status === "completed") {
          if (mode === "preview") {
            await showSingleFramePreview(job.preview);
            showToast("单帧预览完成");
            if (state.previewQueued) {
              state.previewQueued = false;
              schedulePreviewRender(0);
            }
          } else {
            await loadArtifacts();
            showToast("SpriteSheet 构建完成");
          }
        } else {
          showToast(mode === "preview" ? "预览失败，请查看日志" : "构建失败，请查看日志");
        }
      }
    } catch (error) {
      window.clearInterval(state.jobTimer);
      if (mode === "preview") {
        setBusy(elements.previewButton, false, "单帧预览");
      } else {
        setBusy(elements.buildButton, false, "构建选中动画");
      }
      showToast(error.message);
    }
  };
  update();
  state.jobTimer = window.setInterval(update, 700);
}

function renderJob(job) {
  elements.jobStage.textContent = job.stage;
  elements.jobState.textContent = job.status.toUpperCase();
  elements.jobState.className = `job-state ${job.status}`;
  elements.progressBar.className = `progress-bar ${job.status}`;
  elements.buildLog.textContent = job.logs.length ? job.logs.join("\n") : "任务已创建…";
  elements.buildLog.scrollTop = elements.buildLog.scrollHeight;
}

async function loadArtifacts() {
  const payload = await api("/api/artifacts");
  state.artifacts = payload.artifacts;
  renderArtifactTabs();
  if (state.artifacts.length) {
    await selectArtifact(state.artifacts[0]);
  } else {
    state.currentArtifact = null;
    state.previewImage = null;
    state.previewNormalImage = null;
    state.previewMaterialIdImage = null;
    state.previewMetadata = null;
    elements.previewInfo.textContent = "等待构建";
    elements.sheetImage.classList.remove("ready");
    drawPreviewFrame();
  }
}

function renderArtifactTabs() {
  elements.artifactTabs.replaceChildren();
  for (const artifact of state.artifacts) {
    const button = document.createElement("button");
    button.className = "artifact-tab";
    button.textContent = artifact.animation;
    button.dataset.animation = artifact.animation;
    button.addEventListener("click", () => selectArtifact(artifact));
    elements.artifactTabs.append(button);
  }
}

async function selectArtifact(artifact) {
  state.currentArtifact = artifact;
  state.previewFrame = 0;
  state.previewLastTime = 0;
  for (const button of elements.artifactTabs.querySelectorAll(".artifact-tab")) {
    button.classList.toggle("active", button.dataset.animation === artifact.animation);
  }

  const cacheKey = `v=${artifact.modified_at}`;
  const [metadata, colorImage, normalImage, materialIdImage] = await Promise.all([
    fetch(`${artifact.metadata_url}?${cacheKey}`).then((response) => response.json()),
    loadImage(`${artifact.color_url}?${cacheKey}`),
    artifact.normal_url ? loadImage(`${artifact.normal_url}?${cacheKey}`) : Promise.resolve(null),
    artifact.material_id_url ? loadImage(`${artifact.material_id_url}?${cacheKey}`) : Promise.resolve(null),
  ]);
  state.previewMetadata = metadata;
  state.previewImage = colorImage;
  state.previewNormalImage = normalImage;
  state.previewMaterialIdImage = materialIdImage;
  updateSheetImage();
  elements.sheetImage.classList.add("ready");
  elements.previewInfo.textContent = `${artifact.animation} · ${metadata.frame_count} 帧 · ${state.previewMode}`;
  drawPreviewFrame();
}

async function showSingleFramePreview(preview) {
  const cacheKey = `v=${preview.modified_at}`;
  const [colorImage, normalImage, materialIdImage] = await Promise.all([
    loadImage(`${preview.color_url}?${cacheKey}`),
    loadImage(`${preview.normal_url}?${cacheKey}`),
    loadImage(`${preview.material_id_url}?${cacheKey}`),
  ]);
  state.currentArtifact = preview;
  state.previewImage = colorImage;
  state.previewNormalImage = normalImage;
  state.previewMaterialIdImage = materialIdImage;
  state.previewMetadata = {
    frame_count: 1,
    frames: [{ index: 0, x: 0, y: 0, width: preview.size, height: preview.size }],
  };
  state.previewFrame = 0;
  state.previewLastTime = 0;
  for (const button of elements.artifactTabs.querySelectorAll(".artifact-tab")) {
    button.classList.remove("active");
  }
  updatePreviewInfo();
  updateSheetImage();
  elements.sheetImage.classList.add("ready");
  drawPreviewFrame();
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = url;
  });
}

function drawPreviewFrame() {
  const canvas = elements.previewCanvas;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (!state.previewImage || !state.previewMetadata?.frames?.length) return;
  context.imageSmoothingEnabled = false;

  const frame = state.previewMetadata.frames[state.previewFrame % state.previewMetadata.frames.length];
  const baseDestinationSize = Math.min(canvas.width, canvas.height) * 0.82;
  const transform = previewFramingTransform();
  const destinationSize = baseDestinationSize * transform.scale;
  const pixelScale = baseDestinationSize / Math.max(frame.width, 1);
  const x = (canvas.width - destinationSize) / 2 + transform.dx * pixelScale;
  const y = (canvas.height - destinationSize) / 2 + transform.dy * pixelScale;
  let sourceImage = state.previewImage;
  let sourceX = frame.x;
  let sourceY = frame.y;
  if (state.previewMode === "normal" && state.previewNormalImage) {
    sourceImage = state.previewNormalImage;
  } else if (state.previewMode === "material_id" && state.previewMaterialIdImage) {
    sourceImage = state.previewMaterialIdImage;
  } else if (state.previewMode === "composite" && state.previewNormalImage) {
    sourceImage = composeFrame(frame);
    sourceX = 0;
    sourceY = 0;
  }
  context.drawImage(
    sourceImage,
    sourceX,
    sourceY,
    frame.width,
    frame.height,
    x,
    y,
    destinationSize,
    destinationSize
  );
}

function previewFramingTransform() {
  const action = activeAction();
  if (!action || action.name !== state.currentArtifact?.animation) {
    return { dx: 0, dy: 0, scale: 1 };
  }
  const desired = action.framing || { dx: 0, dy: 0, scale: 1 };
  const baseline = state.currentArtifact?.framing || { dx: 0, dy: 0, scale: 1 };
  const baselineScale = Math.max(Number(baseline.scale) || 1, 0.05);
  return {
    dx: (Number(desired.dx) || 0) - (Number(baseline.dx) || 0),
    dy: (Number(desired.dy) || 0) - (Number(baseline.dy) || 0),
    scale: Math.max(Number(desired.scale) || 1, 0.05) / baselineScale,
  };
}

function composeFrame(frame) {
  const canvas = document.createElement("canvas");
  canvas.width = frame.width;
  canvas.height = frame.height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(state.previewImage, frame.x, frame.y, frame.width, frame.height, 0, 0, frame.width, frame.height);
  const colorPixels = context.getImageData(0, 0, frame.width, frame.height);
  context.clearRect(0, 0, frame.width, frame.height);
  context.drawImage(state.previewNormalImage, frame.x, frame.y, frame.width, frame.height, 0, 0, frame.width, frame.height);
  const normalPixels = context.getImageData(0, 0, frame.width, frame.height);
  const light = normalizeVector(state.previewLight);

  for (let index = 0; index < colorPixels.data.length; index += 4) {
    if (colorPixels.data[index + 3] === 0) continue;
    const normalX = normalPixels.data[index] / 127.5 - 1;
    const normalY = normalPixels.data[index + 1] / 127.5 - 1;
    const normalZ = normalPixels.data[index + 2] / 127.5 - 1;
    const diffuse = Math.max(0, normalX * light.x + normalY * light.y + normalZ * light.z);
    const toon = diffuse > 0.72 ? 1.08 : diffuse > 0.38 ? 0.82 : 0.58;
    colorPixels.data[index] = Math.min(255, colorPixels.data[index] * toon);
    colorPixels.data[index + 1] = Math.min(255, colorPixels.data[index + 1] * toon);
    colorPixels.data[index + 2] = Math.min(255, colorPixels.data[index + 2] * toon);
  }
  context.putImageData(colorPixels, 0, 0);
  return canvas;
}

function normalizeVector(vector) {
  const length = Math.hypot(vector.x, vector.y, vector.z) || 1;
  return { x: vector.x / length, y: vector.y / length, z: vector.z / length };
}

function setPreviewMode(mode) {
  state.previewMode = mode;
  for (const button of elements.previewModes.querySelectorAll(".mode-button")) {
    button.classList.toggle("active", button.dataset.mode === mode);
  }
  updatePreviewInfo();
  updateSheetImage();
  drawPreviewFrame();
}

function updatePreviewInfo() {
  if (!state.currentArtifact || !state.previewMetadata) return;
  if (state.currentArtifact.is_preview) {
    elements.previewInfo.textContent = `单帧预览 · ${state.currentArtifact.source_action} · ${state.previewMode}`;
  } else {
    elements.previewInfo.textContent = `${state.currentArtifact.animation} · ${state.previewMetadata.frame_count} 帧 · ${state.previewMode}`;
  }
}

function updateSheetImage() {
  if (!state.currentArtifact) return;
  const artifact = state.currentArtifact;
  let url = artifact.color_url;
  if (state.previewMode === "normal" && artifact.normal_url) url = artifact.normal_url;
  if (state.previewMode === "material_id" && artifact.material_id_url) url = artifact.material_id_url;
  elements.sheetImage.src = `${url}?v=${artifact.modified_at}`;
}

function animatePreview(timestamp) {
  if (state.previewPlaying && state.previewMetadata?.frames?.length) {
    const action = state.actions.find((item) => item.name === state.currentArtifact?.animation);
    const fps = action?.fps || state.config?.animation_fps?.[state.currentArtifact?.animation] || state.config?.fps || 12;
    const frameDuration = 1000 / fps;
    if (!state.previewLastTime || timestamp - state.previewLastTime >= frameDuration) {
      state.previewFrame = (state.previewFrame + 1) % state.previewMetadata.frames.length;
      state.previewLastTime = timestamp;
      drawPreviewFrame();
    }
  }
  window.requestAnimationFrame(animatePreview);
}

elements.scanButton.addEventListener("click", scanActions);
elements.previewButton.addEventListener("click", startPreview);
elements.buildButton.addEventListener("click", startBuild);
elements.saveButton.addEventListener("click", () => saveConfig().catch((error) => showToast(error.message)));
elements.playButton.addEventListener("click", () => {
  state.previewPlaying = !state.previewPlaying;
  elements.playButton.textContent = state.previewPlaying ? "❚❚" : "▶";
});
elements.frameOffsetX.addEventListener("input", updateActiveFraming);
elements.frameOffsetY.addEventListener("input", updateActiveFraming);
elements.frameScale.addEventListener("input", updateActiveFraming);
elements.previewModes.addEventListener("click", (event) => {
  const button = event.target.closest(".mode-button");
  if (button) setPreviewMode(button.dataset.mode);
});
elements.previewStage.addEventListener("pointermove", (event) => {
  if (state.previewMode !== "composite") return;
  const bounds = elements.previewStage.getBoundingClientRect();
  state.previewLight.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
  state.previewLight.y = -(((event.clientY - bounds.top) / bounds.height) * 2 - 1);
  state.previewLight.z = 0.82;
  drawPreviewFrame();
});

async function initialize() {
  try {
    await loadConfig();
    renderFramingControls();
    elements.playButton.textContent = state.previewPlaying ? "❚❚" : "▶";
    await loadArtifacts();
    window.requestAnimationFrame(animatePreview);
  } catch (error) {
    document.querySelector("#serverStatus").textContent = "连接失败";
    document.querySelector("#serverStatus").style.color = "var(--red)";
    showToast(error.message);
  }
}

initialize();
