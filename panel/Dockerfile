FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 7860
CMD ["panel", "serve", "app.py", "--port", "7860", \
     "--address", "0.0.0.0", "--allow-websocket-origin=*"]
