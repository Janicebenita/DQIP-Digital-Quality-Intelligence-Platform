FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt
RUN python -m playwright install --with-deps chromium

COPY app.py /app/app.py
COPY analytics.py /app/analytics.py
COPY storytelling.py /app/storytelling.py
COPY video_renderer.py /app/video_renderer.py
COPY voice_generator.py /app/voice_generator.py
COPY screen_recorder.py /app/screen_recorder.py
COPY subtitle_generator.py /app/subtitle_generator.py
COPY scene_manager.py /app/scene_manager.py
COPY sample_script.py /app/sample_script.py
COPY ["SQC Data.xls", "/app/SQC Data.xls"]
COPY ["DQIP_Cross_Domain_Sample_Data.xlsx", "/app/DQIP_Cross_Domain_Sample_Data.xlsx"]
COPY sample_data /app/sample_data

EXPOSE 8501

ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLE_CORS=false
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

CMD ["streamlit", "run", "/app/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--server.enableCORS=false", "--server.enableXsrfProtection=false", "--browser.gatherUsageStats=false"]
