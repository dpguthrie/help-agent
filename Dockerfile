FROM python:3.12-slim

RUN pip install uv

WORKDIR /app
COPY pyproject.toml .
RUN uv pip install --system --no-cache .

COPY src/ src/
COPY .chainlit/ .chainlit/ 2>/dev/null || true

EXPOSE 8000
CMD ["chainlit", "run", "src/app.py", "--host", "0.0.0.0", "--port", "8000"]
