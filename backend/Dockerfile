FROM python:3.12-slim

WORKDIR /app

# Copy full source first so hatchling can locate the package
COPY . .

# Install the package with all dependencies
RUN pip install --no-cache-dir -e "."

CMD ["uvicorn", "flowforge.main:app", "--host", "0.0.0.0", "--port", "8000"]
