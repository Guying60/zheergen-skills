# 转录脚本技术架构

## 脚本位置
`~/meeting-recording/scripts/transcribe.py`

## 技术栈
- **VAD**: fsmn-vad (语音活动检测，切分语音段)
- **ASR**: SenseVoiceSmall (多语言语音识别)
- **声纹**: cam++ (说话人 embedding 提取)
- **聚类**: AgglomerativeClustering (sklearn，无监督说话人分离)

## 处理流程

```
输入音频
    │
    ▼
[1/4] VAD 分段
    │  fsmn-vad 单独运行
    │  输出: [(start_ms, end_ms), ...]
    │  约 808 段 / 51分钟录音
    │
    ▼
[2/4] 加载模型
    │  音频重采样到 16kHz 单声道
    │  加载 SenseVoiceSmall + cam++
    │
    ▼
[3/4] 逐段处理 (循环)
    │  对每个 VAD 段:
    │  ├─ 提取音频切片 (内存操作，无 ffmpeg)
    │  ├─ 写临时 WAV → SenseVoice ASR → 文字
    │  ├─ 写临时 WAV → cam++ → 声纹 embedding (1D 向量)
    │  └─ 收集 (文字, embedding, 时间戳)
    │
    ▼
[4/4] 说话人聚类
    │  AgglomerativeClustering
    │  metric=cosine, linkage=average
    │  n_clusters = min(max(2, len/10), 6)
    │  输出: SPEAKER_XX 标签
    │
    ▼
合并连续同说话人段落
    │
    ▼
输出: 转录.txt
```

## 关键设计决策

### 为什么用 VAD-first 而非 merge_vad=False?
SenseVoice 的 `merge_vad=False` 对连续语音不可靠，常返回单个结果且无时间戳。单独运行 VAD 模型可获得可靠的分段时间。

### 为什么逐段提取 embedding 而非按大块?
5 分钟大块内可能有多个说话人，embedding 会被平均化，导致聚类效果差。逐 VAD 段（2-60秒）提取可精确区分说话人。

### 性能数据 (51分钟/48MB mp3)
- VAD: ~14s
- 模型加载: ~50s
- ASR + cam++: ~260s
- 聚类: <1s
- **总计: ~5分钟**

## 已知 Bug

**嵌套目录问题**: 当传入路径已在会议文件夹内时，脚本会创建嵌套目录。
- 错误示例: `会议录音/2026-06-21/01_团队周会/录音/2026-06-21/01_1/`
- 原因: 脚本将文件名解析为 `YYYY-MM-DD_主题` 格式并建新目录
- 解决: 传入会议文件夹路径（方式二）或手动整理

## 依赖
```bash
~/funasr-env/bin/pip install funasr numpy scikit-learn soundfile scipy onnxruntime
```
系统依赖: `ffmpeg`
