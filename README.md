# SayType - 语音输入法

> Windows 桌面语音输入工具：按住快捷键说话，文字自动出现在任意应用的光标处。

## 核心特性

**使用体验**
- 按住一个键说话（默认 `F2`），松开即出字 —— PTT 模式，所见即所得
- 文字注入任意应用：剪贴板 + Ctrl+V 兼容微信 / Word / 浏览器 / IDE / 终端
- 边说边在屏幕底部的悬浮条上看到识别中的文字

**识别能力**
- 三种 ASR 引擎按需切换 —— 本地流式 / 本地离线 / 讯飞云端
- 15 条内置 **语音指令**：说"换行/句号/全选/撤销"直接执行按键，而不是键入字面字符
- 可选 **LLM 润色**：DeepSeek / OpenAI 兼容 API，把口语自动整理为书面表达
- **本地历史**：每次识别自动入库，托盘 → 历史 即可翻看 / 复制 / 再次注入

**本地优先**
- 默认全离线、零成本可用；网络模式仅在选讯飞时启用
- 配置与历史都存在 `~/.voice_input/`，不上传任何服务器

## 快速上手

```bash
pip install -r requirements.txt
python main.py    # 或双击 run.bat
```

1. 看到系统托盘出现麦克风图标 —— 已启动
2. 把光标放到任意输入框，**按住 `F2`** 开始说话，悬浮条会实时显示识别文字
3. **松开 `F2`** —— 文字自动粘贴到光标处

需要回看刚才说过的内容？托盘右键 → **历史…**，选行可复制或再次注入到光标。

> 首次启动会自动下载 FunASR 模型（约 800MB），下面的「安装」章节有镜像与故障排查。

## 安装

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

首次启动会自动下载 FunASR 模型（流式 + 标点模型，合计约 800MB）到 `~/.cache/modelscope/`。

## 设置

托盘右键 → 设置：
- 全局热键（如 `f2`、`f9`、`ctrl+space`）
- ASR 引擎选择（流式 / 离线 / 讯飞云）
- 语音指令开关
- LLM 润色开关 + API Key
- 讯飞凭据（如使用云端）
- 自定义术语词库
- **历史相关**：是否保存历史、保留上限条数、是否同时记录润色后文本

配置存储于 `~/.voice_input/config.json`。

## 历史记录

每次识别成功后会自动入库（语音指令不计入）。**托盘右键 → 历史…** 打开查看器：

- 表格按时间倒序排列，每行显示 时间 / 注入文本 / 引擎；启用了润色时，悬停文本可看到 ASR 原文
- **复制**：把选中行的文本写入剪贴板
- **再次注入**：关闭窗口后自动 `Ctrl+V` 到之前的应用 —— 常用回复一键重发
- **清空全部**：二次确认后删除历史文件

历史以 JSONL 格式存放在 `~/.voice_input/history.jsonl`，每行一条：

```json
{"ts": "2026-05-25T14:32:10.123+08:00", "original": "你好世界", "polished": null, "backend": "funasr_streaming"}
```

可在设置面板里：关闭整个历史（`history_enabled`）、调整保留上限（`history_max`，默认 500）、控制是否同时记录润色后文本（`history_record_polish`）。数据完全保存在本地，不上传任何服务器。

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
postprocess/history.py       # 本地历史记录持久化 (JSONL)
injector/text_injector.py    # 剪贴板注入
ui/floating_bar.py           # 屏幕底部悬浮状态条
ui/tray.py                   # 系统托盘
ui/settings_dialog.py        # 设置面板
ui/history_dialog.py         # 历史查看弹窗
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
- **历史窗口空白**：确认设置面板里「保存识别历史」已勾选，且 `~/.voice_input/history.jsonl` 存在
