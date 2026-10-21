FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn google-genai
COPY crystal/ crystal/
ENV CRYSTAL_DATA=real PYTHONUTF8=1
EXPOSE 8765
CMD ["uvicorn", "crystal.web.app:app", "--host", "0.0.0.0", "--port", "8765"]
