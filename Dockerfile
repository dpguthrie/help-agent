FROM python:3.12-slim

RUN pip install uv

WORKDIR /app
COPY . .
RUN uv pip install --system --no-cache .

EXPOSE 8000
CMD ["chainlit", "run", "src/app.py", "--host", "0.0.0.0", "--port", "8000"]
