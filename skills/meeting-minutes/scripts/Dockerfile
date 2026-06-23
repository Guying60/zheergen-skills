FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/funasr-env && \
    /opt/funasr-env/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/funasr-env/bin/pip install --no-cache-dir \
        funasr numpy scikit-learn scipy soundfile onnxruntime

RUN mkdir -p /root/meeting-recording/会议录音

COPY transcribe.py /opt/transcribe.py

ENV PATH="/opt/funasr-env/bin:$PATH"
WORKDIR /root/meeting-recording

ENTRYPOINT ["python3", "/opt/transcribe.py"]
