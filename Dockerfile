# linux-mail-agent container image.
# It is primarily useful for MCP over SSE/HTTP, or for keeping the agent
# isolated from the host. For stdio MCP, installing on the host is simpler.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 mailagent
USER mailagent

ENTRYPOINT ["mailagent"]
CMD ["serve", "--transport", "stdio"]
