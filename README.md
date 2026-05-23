# 语音输入法 (Voice Input Method)

一个 Windows 桌面端语音输入工具，按住快捷键说话，自动将识别文本注入到当前光标所在的任意应用（微信 / Word / 浏览器 / IDE 等）。

## 核心特性

- **任意应用注入**：通过剪贴板 + Ctrl+V 兼容所有 Windows 应用
- **全局快捷键**：默认 `F2` 按住说话，松开出字
- **本地零成本**：FunASR (Paraformer-zh + VAD + 标点) 本地推理，断网可用
- **语音指令**：说"换行/句号/删除/全选/保存"等直接执行动作
- **LLM 润色（可选）**：口语 → 书面，纠错；按需开关控制成本
- **悬浮反馈**：屏幕底部状态条显示录音/识别状态

## 安装

```bash
pip install -r requirements.txt
```

首次启动会自动下载 FunASR 模型（约 500MB）到 `~/.cache/modelscope/`。

## 启动

```bash
python main.py
```

或双击 `run.bat`。

启动后系统托盘出现麦克风图标。**按住 F2** 开始说话，**松开** 自动识别并写入当前光标位置。

## 配置

托盘右键 → 设置。可修改：
- 全局热键（如 `f2`、`f9`）
- ASR 引擎
- 语音指令开关
- LLM 润色（需填 DeepSeek / OpenAI 兼容 API Key）
- 自定义术语词库

配置保存在 `~/.voice_input/config.json`。

## 目录结构

```
audio/recorder.py        # 麦克风采集
asr/funasr_local.py      # 本地 FunASR 后端
postprocess/commands.py  # 语音指令解析
postprocess/llm_polish.py# LLM 润色
injector/text_injector.py# 剪贴板注入
ui/floating_bar.py       # 悬浮状态条
ui/tray.py               # 系统托盘
ui/settings_dialog.py    # 设置面板
main.py                  # 入口 + 控制器
```

## 下一步（路线图）

- 流式实时显示（paraformer-zh-streaming）
- 云端 ASR 后端（讯飞 / 阿里云）
- PyInstaller 打包成单 exe
- 多组合键热键支持
