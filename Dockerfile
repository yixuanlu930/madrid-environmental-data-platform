
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY notebooks ./notebooks
ENV PYTHONPATH=/app
EXPOSE 8000 8888
CMD ["python", "src/server.py"]
