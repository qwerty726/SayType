# SayType - 语音输入法

> Windows 桌面语音输入工具：按住快捷键说话，文字自动出现在任意应用的光标处。

## 核心特性

- **任意应用注入**：剪贴板 + Ctrl+V，兼容微信 / Word / 浏览器 / IDE / 终端
- **全局快捷键**：默认 `F2` 按住说话，松开出字
- **流式实时显示**：边说边在悬浮条显示识别中的文字（基于 paraformer-zh-streaming）
- **三种 ASR 引擎可切换**
  - **本地 FunASR 流式**（默认，推荐）：边说边出字，断网可用，准确度 92%+
  - **本地 FunASR 离线**：整句识别，最稳，准确度 92%+
  - **讯飞云端**：准确度 96%+、延迟最低，需配置 API 凭据
- **语音指令**：说"换行/句号/删除/全选/保存/撤销"等直接执行动作（15 条内置）
- **LLM 润色（可选）**：DeepSeek / OpenAI 兼容 API，把口语整理为书面表达
- **零成本可离线**：本地模式不依赖网络、不调任何付费 API

## 安装

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

首次启动会自动下载 FunASR 模型（流式 + 标点模型，合计约 800MB）到 `~/.cache/modelscope/`。

## 启动

```bash
python main.py
```

或双击 `run.bat`。

启动后：
- 系统托盘出现麦克风图标
- **按住 F2** 开始说话，悬浮条出现并显示实时识别文字
- **松开** 自动注入文字到当前光标位置

## 设置

托盘右键 → 设置：
- 全局热键（如 `f2`、`f9`、`ctrl+space`）
- ASR 引擎选择（流式 / 离线 / 讯飞云）
- 语音指令开关
- LLM 润色开关 + API Key
- 讯飞凭据（如使用云端）
- 自定义术语词库

配置存储于 `~/.voice_input/config.json`。

## 讯飞云端配置

1. 注册 [讯飞开放平台](https://www.xfyun.cn/)
2. 创建"语音听写（流式版）"应用
3. 把 `APPID` / `APIKey` / `APISecret` 填入设置面板
4. 切换 ASR 引擎为"讯飞云端"

免费额度：500 次/天。付费：约 ¥0.0015/秒。

## 语音指令

说出以下短语会触发动作而非键入字面字符：

| 指令 | 动作 |
|---|---|
| 换行 / 回车 | 按 Enter |
| 空格 | 按 Space |
| 删除 / 退格 | 按 Backspace |
| 全选 / 复制 / 粘贴 / 撤销 / 保存 | Ctrl+A/C/V/Z/S |
| 句号 / 逗号 / 问号 / 感叹号 / 冒号 / 分号 / 顿号 | 插入对应中文标点 |

## 打包成 exe

```bash
build.bat
```

输出：`dist\SayType\SayType.exe`。整个 `dist\SayType\` 文件夹（约 1.5-3 GB）可拷贝到没装 Python 的机器运行；FunASR 模型仍是首次启动联网下载。

## 目录结构

```
audio/recorder.py            # 麦克风采集，PTT 模式
asr/base.py                  # ASR 后端抽象接口
asr/funasr_local.py          # 本地离线（paraformer-zh + VAD + 标点）
asr/funasr_streaming.py      # 本地流式（paraformer-zh-streaming + 标点）
asr/xunfei_cloud.py          # 讯飞 WebSocket 实时流式
postprocess/commands.py      # 语音指令解析
postprocess/llm_polish.py    # LLM 润色
injector/text_injector.py    # 剪贴板注入
ui/floating_bar.py           # 屏幕底部悬浮状态条
ui/tray.py                   # 系统托盘
ui/settings_dialog.py        # 设置面板
main.py                      # 入口 + Controller (热键/录音/ASR/注入 协调)
voice_input.spec             # PyInstaller 打包配置
```

## 性能指标

| 指标 | 本地流式 | 本地离线 | 讯飞云端 |
|---|---|---|---|
| 首字延迟 | ~600ms | 录完后 ~800ms | ~200ms |
| 整句准确度 | 92%+ | 92%+ | 96%+ |
| 网络要求 | 不需要 | 不需要 | 必需 |
| 成本 | 0 | 0 | ¥0.0015/秒 |
| 内存占用 | ~1GB | ~700MB | ~50MB |

## 故障排查

- **F2 没反应**：以管理员身份运行（`keyboard` 库注册全局热键需要权限）
- **模型下载失败**：手动设置 ModelScope 镜像
  ```bash
  set MODELSCOPE_DOMAIN=www.modelscope.cn
  ```
- **讯飞报 11201**：每日免费额度用完，换 API Key 或购买
- **打包后启动报缺 DLL**：通常是 torch 的 mkl/cuDNN 缺失，把整个 `dist\SayType\` 都拷过去
