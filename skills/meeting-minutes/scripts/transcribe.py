#!/usr/bin/env python3
"""
会议录音 ASR 转录
================

SenseVoice + fsmn-vad + CAM++ 说话人分离

用法:
    # 单个录音/视频（自动建文件夹、移入、转录）
    python3 transcribe.py 会议录音/2026-06-21_团队周会.mp3
    python3 transcribe.py 会议录音/2026-06-21_团队周会.mp4

    # 多个文件（放入文件夹后转录，自动合并）
    python3 transcribe.py 会议录音/2026-06-21/01_团队周会/

支持格式:
    音频: mp3, wav, m4a, flac, ogg
    视频: mp4, avi, mkv, mov, webm (自动提取音频)

目录结构:
    会议录音/
    └── 2026-06-21/
        └── 01_团队周会/
            ├── 录音/
            │   ├── 1.mp3
            │   └── 2.mp3       (可多个，脚本自动合并)
            ├── 转录.txt
            └── 纪要.md         (由 Hermes Agent 生成)
"""

import re, sys, time, os, glob, shutil, warnings
warnings.filterwarnings("ignore")
import numpy as np


def fmt_ts(ms):
    s = int(ms / 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# 支持的文件格式
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm"}
ALL_MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS


def is_video(filepath):
    """判断文件是否为视频格式。"""
    return os.path.splitext(filepath)[1].lower() in VIDEO_EXTS


def extract_audio_from_video(video_path, output_path):
    """用 ffmpeg 从视频中提取音频，输出为 mp3。"""
    import subprocess
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn",                # 不要视频流
        "-acodec", "libmp3lame",
        "-ar", "16000",       # 16kHz 采样率
        "-ac", "1",           # 单声道
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: ffmpeg 提取音频失败: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return output_path


def find_next_seq(parent_dir, date_str):
    """在日期文件夹下找到下一个序号，如 01、02、03..."""
    date_dir = os.path.join(parent_dir, date_str)
    if not os.path.isdir(date_dir):
        return "01"
    existing = sorted(glob.glob(os.path.join(date_dir, "??_*")))
    if not existing:
        return "01"
    last = os.path.basename(existing[-1]).split("_")[0]
    return f"{int(last) + 1:02d}"


def setup_single_audio(media_path):
    """
    单个录音/视频：创建目录结构，移入文件，返回会议目录路径。

    情况一：文件已在会议目录中
      输入: /path/to/2026-06-21/01_团队周会/录音/1.mp3
      直接返回: /path/to/2026-06-21/01_团队周会/

    情况二：文件是独立文件
      输入: /path/to/2026-06-21_团队周会.mp4
      创建: /path/to/2026-06-21/01_团队周会/录音/1.mp4
    """
    media_path = os.path.abspath(media_path)
    parent_dir = os.path.dirname(media_path)
    filename = os.path.splitext(os.path.basename(media_path))[0]
    ext = os.path.splitext(media_path)[1].lower()

    # 情况一：检查是否已在 录音/ 子目录中（即会议目录结构已存在）
    if os.path.basename(parent_dir) == "录音":
        meeting_dir = os.path.dirname(parent_dir)
        # 确认会议目录结构正确（包含 录音/ 子目录）
        if os.path.isdir(os.path.join(meeting_dir, "录音")):
            print(f"[信息] 使用已有会议目录: {meeting_dir}", file=sys.stderr)
            return meeting_dir

    # 情况二：独立文件，需要创建目录结构
    # 解析日期和主题：YYYY-MM-DD_主题
    if "_" in filename and len(filename.split("_")[0]) == 10:
        parts = filename.split("_", 1)
        date_str = parts[0]
        topic = parts[1] if len(parts) > 1 else "会议"
    else:
        date_str = time.strftime("%Y-%m-%d")
        topic = filename

    # 建目录
    seq = find_next_seq(parent_dir, date_str)
    meeting_dir = os.path.join(parent_dir, date_str, f"{seq}_{topic}")
    recording_dir = os.path.join(meeting_dir, "录音")
    os.makedirs(recording_dir, exist_ok=True)

    # 移动文件（保留原始扩展名）
    dest = os.path.join(recording_dir, f"1{ext}")
    if os.path.abspath(media_path) != os.path.abspath(dest):
        shutil.move(media_path, dest)
        print(f"[整理] 文件移入: {dest}", file=sys.stderr)

    return meeting_dir


def setup_folder(folder_path):
    """
    文件夹模式：直接使用该文件夹作为会议目录。
    录音从 录音/ 子目录读取。
    """
    folder_path = os.path.abspath(folder_path)
    if not os.path.isdir(folder_path):
        print(f"Error: 目录不存在: {folder_path}", file=sys.stderr)
        sys.exit(1)
    return folder_path


def get_audio_files(meeting_dir):
    """
    获取会议目录下 录音/ 子目录中的所有媒体文件。
    视频文件会自动提取音频。
    按文件名排序返回音频文件路径列表。
    """
    recording_dir = os.path.join(meeting_dir, "录音")
    if not os.path.isdir(recording_dir):
        print(f"Error: 录音目录不存在: {recording_dir}", file=sys.stderr)
        sys.exit(1)

    # 收集所有媒体文件
    all_files = []
    for ext in ALL_MEDIA_EXTS:
        all_files.extend(glob.glob(os.path.join(recording_dir, f"*{ext}")))
        all_files.extend(glob.glob(os.path.join(recording_dir, f"*{ext.upper()}")))
    all_files = sorted(set(all_files))

    if not all_files:
        print(f"Error: 录音目录为空: {recording_dir}", file=sys.stderr)
        sys.exit(1)

    # 视频文件提取音频
    audio_files = []
    for f in all_files:
        if is_video(f):
            audio_path = os.path.splitext(f)[0] + ".mp3"
            if not os.path.exists(audio_path):
                print(f"[提取] {os.path.basename(f)} → {os.path.basename(audio_path)}", file=sys.stderr)
                extract_audio_from_video(f, audio_path)
            audio_files.append(audio_path)
        else:
            audio_files.append(f)

    return audio_files


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = sys.argv[1]

    # 判断输入是文件还是文件夹
    if os.path.isdir(input_path):
        meeting_dir = setup_folder(input_path)
    elif os.path.isfile(input_path):
        meeting_dir = setup_single_audio(input_path)
    else:
        print(f"Error: 不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    audio_files = get_audio_files(meeting_dir)
    out_path = os.path.join(meeting_dir, "转录.txt")

    print(f"[信息] 会议目录: {meeting_dir}", file=sys.stderr)
    print(f"[信息] 录音文件: {len(audio_files)} 个", file=sys.stderr)
    for f in audio_files:
        print(f"        - {os.path.basename(f)}", file=sys.stderr)

    from funasr import AutoModel
    import soundfile as sf

    # ── Step 1: VAD（对每个录音分别做，合并结果）──
    print("[1/4] VAD 语音活动检测...", file=sys.stderr)
    t0 = time.time()
    vad_model = AutoModel(model='iic/speech_fsmn_vad_zh-cn-16k-common-pytorch', trust_remote_code=True)

    all_vad_segs = []  # (start_ms, end_ms, audio_file_index)
    offset_ms = 0

    for fi, audio_file in enumerate(audio_files):
        vad_result = vad_model.generate(input=audio_file)
        for item in vad_result:
            if 'value' in item:
                for seg in item['value']:
                    if isinstance(seg, list) and len(seg) == 2:
                        start, end = seg[0] + offset_ms, seg[1] + offset_ms
                        if end - start >= 200:
                            all_vad_segs.append((start, end, fi))

        # 获取音频时长作为偏移
        info = sf.info(audio_file)
        offset_ms += int(info.duration * 1000)

    print(f"[1/4] VAD: {len(all_vad_segs)} 段 ({time.time()-t0:.1f}s)", file=sys.stderr)

    # ── Step 2: 加载所有音频到内存 ──
    print("[2/4] 加载音频和模型...", file=sys.stderr)
    all_audio = []
    sr = None
    for audio_file in audio_files:
        data, sr = sf.read(audio_file)
        if len(data.shape) > 1:
            data = data.mean(axis=1)
        if sr != 16000:
            import scipy.signal
            data = scipy.signal.resample(data, int(len(data) * 16000 / sr))
            sr = 16000
        all_audio.append(data)

    asr_model = AutoModel(model='iic/SenseVoiceSmall', trust_remote_code=True)
    sd_model = AutoModel(model='iic/speech_campplus_sv_zh-cn_16k-common', trust_remote_code=True)
    print(f"[2/4] 就绪 ({time.time()-t0:.1f}s)", file=sys.stderr)

    # 计算每个录音的起始样本偏移
    audio_offsets = []
    cumulative = 0
    for data in all_audio:
        audio_offsets.append(cumulative)
        cumulative += len(data)
    total_samples = cumulative

    # ── Step 3: 逐段 ASR + embedding ──
    tmp_wav = "/tmp/meeting_seg_tmp.wav"
    print(f"[3/4] 转录中...", file=sys.stderr)
    t2 = time.time()
    segments = []
    embeddings = []

    for i, (vad_start_ms, vad_end_ms, fi) in enumerate(all_vad_segs):
        start_sample = int(vad_start_ms / 1000 * sr) - audio_offsets[fi]
        end_sample = min(int(vad_end_ms / 1000 * sr) - audio_offsets[fi], len(all_audio[fi]))
        chunk = all_audio[fi][start_sample:end_sample]
        if len(chunk) < sr * 0.2:
            continue

        sf.write(tmp_wav, chunk, sr)

        # ASR
        asr_results = asr_model.generate(input=tmp_wav, merge_vad=False, batch_size_s=60)
        text = ""
        for r in asr_results:
            raw = r.get('text', '')
            clean = re.sub(r'<\|[^|]*\|>', '', raw).strip()
            if clean:
                text += clean
        if not text:
            continue

        # CAM++ embedding
        emb = None
        try:
            sd_result = sd_model.generate(input=tmp_wav)
            for item in sd_result:
                if isinstance(item, dict):
                    e = item.get("spk_embedding", item.get("embedding"))
                    if e is not None:
                        emb = np.array(e).squeeze()
                        if emb.ndim != 1:
                            emb = None
        except:
            pass

        segments.append({"start_ms": vad_start_ms, "end_ms": vad_end_ms, "text": text, "speaker": "SPEAKER_00"})
        embeddings.append(emb)

        if (i + 1) % 50 == 0:
            elapsed = time.time() - t2
            eta = elapsed / (i + 1) * (len(all_vad_segs) - i - 1)
            print(f"    {i+1}/{len(all_vad_segs)} ({elapsed:.0f}s, ~{eta:.0f}s left)", file=sys.stderr)

    print(f"[3/4] 转录完成: {len(segments)} 段 ({time.time()-t2:.1f}s)", file=sys.stderr)

    # ── Step 4: 说话人聚类 ──
    print("[4/4] 说话人聚类...", file=sys.stderr)
    t3 = time.time()
    valid_embs = [(i, e) for i, e in enumerate(embeddings) if e is not None]
    if len(valid_embs) > 2:
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.preprocessing import normalize
        idx_list = [i for i, _ in valid_embs]
        emb_matrix = np.array([e for _, e in valid_embs])
        emb_norm = normalize(emb_matrix)
        n_spk = min(max(2, len(emb_norm) // 10), 6)
        labels = AgglomerativeClustering(n_clusters=n_spk, metric="cosine", linkage="average").fit_predict(emb_norm)
        for j, idx in enumerate(idx_list):
            segments[idx]["speaker"] = f"SPEAKER_{labels[j]:02d}"
        print(f"[4/4] 聚类完成: {n_spk} 个说话人 ({time.time()-t3:.1f}s)", file=sys.stderr)

    # 合并连续同说话人段落
    merged = []
    for seg in segments:
        if merged and merged[-1]["speaker"] == seg["speaker"]:
            merged[-1]["end_ms"] = seg["end_ms"]
            merged[-1]["text"] += seg["text"]
        else:
            merged.append(dict(seg))

    # 写入文件
    with open(out_path, "w", encoding="utf-8") as f:
        for s in merged:
            f.write(f"[{fmt_ts(s['start_ms'])} - {fmt_ts(s['end_ms'])}] {s['speaker']}: {s['text']}\n")

    print(f"\n[完成] {out_path}", file=sys.stderr)
    print(f"[完成] 总耗时: {time.time()-t0:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
