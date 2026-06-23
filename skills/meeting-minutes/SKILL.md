---
name: meeting-minutes
description: "会议录音转录 + 生成纪要：ASR 转录音频为带说话人标签的文本，再由 LLM 推断人名并生成结构化纪要"
version: 1.0.0
author: User
license: MIT
metadata:
  hermes:
    tags: [meeting, minutes, transcription, asr, speaker-diarization, funasr]
    related_skills: []
---

# 会议纪要生成

## Overview

端到端会议纪要流程：
1. **ASR 转录**：FunASR（SenseVoice + fsmn-vad + CAM++）将录音转为带说话人标签的文本
2. **LLM 纪要**：Hermes Agent 读取转录 + 参会人名单，推断 SPEAKER_XX 真实姓名，生成结构化纪要

## When to Use

- 有会议录音需要整理成纪要
- 知道参会人员名单
- 需要区分不同说话人

## 使用方式

用户通过 Hermes Desktop 上传录音，或告知录音路径，加上会议主题和参会人即可。
录音可以在任意位置，不需要放到特定目录。

### Agent 自动流程

当用户说「帮我转录这个会议录音」时，Hermes Agent 执行：

**第一步：ASR 转录**

```bash
SCRIPT=~/.hermes/skills/productivity/meeting-minutes/scripts/transcribe.py
~/funasr-env/bin/python3 "$SCRIPT" "<录音路径>" 2>/dev/null
```

脚本会自动：
- 判断录音日期和主题（从文件名解析，或由用户提供）
- 创建目录结构，移入录音
- 运行 VAD + ASR + 说话人聚类
- 输出 `转录.txt` 到同目录下

转录完成后，脚本输出转录文件的路径。

**第二步：生成纪要**

Agent 读取 `转录.txt`，结合用户提供的参会人名单，推断 SPEAKER_XX 真实姓名，生成结构化纪要，保存为 `纪要.md`。

### 用户视角

```
用户：帮我转录这个录音 /tmp/2026-06-23_产品评审.mp3
     参会人：李华强、董子瑜、姚沅彪、王蒙淇

Hermes：
  [运行转录脚本...]
  [读取转录.txt]
  [推断说话人、生成纪要]
  纪要已生成：/tmp/2026-06-23/01_产品评审/纪要.md
```

### 多个录音

多个文件可以放入同一个文件夹的 `录音/` 子目录，脚本自动合并转录：

```bash
# 手动放入：2026-06-23/01_产品评审/录音/1.mp3, 2.mp3...
~/funasr-env/bin/python3 "$SCRIPT" "2026-06-23/01_产品评审/" 2>/dev/null
```

### 输出结构

脚本在录音所在位置自动创建如下结构：

```
<录音所在目录>/
└── YYYY-MM-DD/
    └── 序号_主题/
        ├── 录音/
        │   ├── 1.mp3
        │   └── 2.mp3       (多个录音自动合并)
        ├── 转录.txt
        └── 纪要.md          (Agent 生成)
```

命名规则：
- 日期文件夹：`YYYY-MM-DD`（从文件名解析，无则用当天日期）
- 会议文件夹：`序号_主题`（如 `01_团队周会`、`02_产品评审`）
- 录音文件夹：`录音/`
- 转录/纪要：固定名称 `转录.txt`、`纪要.md`

## ASR 转录输出格式

```
[00:00:00 - 00:04:27] SPEAKER_02: 转录文本内容...
[00:04:31 - 00:05:25] SPEAKER_01: 转录文本内容...
[00:15:15 - 00:16:01] SPEAKER_02: 转录文本内容...
```

## LLM 推断人名的依据

- 指导、提问、点评 → 团队领导/师兄
- 汇报工作进展 → 根据汇报内容对应成员
- 主持会议、串联流程 → 主持人
- 称呼其他人名字 → 确认说话人身份

## 纪要输出格式

```markdown
# 会议纪要

**时间**：YYYY-MM-DD
**参与人**：姓名1、姓名2、...

---

## 一、主题标题

要点内容...

---

## 后续任务

| 负责人 | 任务 | 优先级 |
|--------|------|--------|
| ... | ... | ... |
```

## Prerequisites

- `~/funasr-env` 虚拟环境，已安装：funasr, numpy, scikit-learn, soundfile, scipy, onnxruntime
- `ffmpeg`（系统已安装，用于视频提取音频）

## 支持格式

- **音频**：mp3, wav, m4a, flac, ogg
- **视频**：mp4, avi, mkv, mov, webm（自动用 ffmpeg 提取音频）

## 安装

首次使用需要安装 FunASR 环境，两种方式任选：

### 方式一：本地安装（推荐）

```bash
bash ~/.hermes/skills/productivity/meeting-minutes/scripts/setup.sh
```

一键完成：创建 `~/funasr-env` 虚拟环境、安装 pip 依赖、检查 ffmpeg。
首次转录时 FunASR 自动下载模型（~3GB），无需手动操作。

### 方式二：Docker

```bash
# 构建镜像（一次性）
cd ~/.hermes/skills/productivity/meeting-minutes/scripts
docker build -t meeting-minutes .

# 使用：挂载录音所在目录
docker run --rm -v "/录音/所在/目录:/data" \
  meeting-minutes /data/会议录音.mp3
```

不污染宿主机，模型每次重新下载（除非额外挂载 `~/.cache/modelscope`）。

## Pitfalls

1. **转录约 5 分钟**（51 分钟录音），VAD + ASR + 说话人聚类全流程
2. **SPEAKER_XX 是聚类编号**，不对应真实姓名，需要 LLM 根据内容推断
3. **转录有错别字**，SenseVoice 模型对同音字可能误识别，纪要中应修正
4. **stderr 必须重定向**，funasr 会把下载进度混入 stdout
5. **脚本嵌套目录 bug**：如果传入的文件路径已在会议文件夹内（如 `会议录音/2026-06-21/01_团队周会/录音/1.mp3`），脚本会错误地创建嵌套目录。解决：传入会议文件夹路径而非录音文件路径，或手动整理目录
6. **cam++ 处理长音频卡死**：>30 分钟的音频不能直接传给 cam++，必须按 VAD 段切分后逐段提取 embedding
7. **onnxruntime 需手动安装**：`~/funasr-env/bin/pip install onnxruntime scikit-learn`

## 技术细节：VAD-First 方案

SenseVoice 的 `merge_vad=False` 参数**不可靠**，对连续语音（会议、讲座）通常只返回一个结果且无时间戳。

**正确方案**：
1. 单独运行 fsmn-vad 获取语音段边界 `[(start_ms, end_ms), ...]`
2. 对每个 VAD 段单独运行 ASR 和 cam++
3. 用 VAD 边界作为时间戳
4. 对所有段的 embedding 做聚类分配说话人标签

这是脚本 `transcribe.py` 的核心实现。

## Speaker 映射策略

Hermes Agent 推断 SPEAKER_XX → 真实姓名的依据：
- **说话内容**：汇报什么工作 → 对应负责该工作的成员
- **语气角色**：指导、提问、点评 → 领导/师兄
- **主持行为**：串联流程、邀请下一位 → 主持人
- **互相称呼**：提到其他人名字时可确认身份
- **发言量**：领导通常发言最多，主持其次
