ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . /app
RUN mkdir -p /app/data /app/workflows && chown -R 1000:1000 /app
USER 1000:1000
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SHOTDESK_HOST=0.0.0.0
EXPOSE 1258
CMD ["python3","-B","/app/server.py"]
