FROM --platform=linux/amd64 ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sudo \
    python3 python3-pip python3-venv python3-dev \
    gdb build-essential \
    git wget curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --upgrade pip

RUN mkdir -p /root/.pip && \
    echo "[global]" > /root/.pip/pip.conf && \
    echo "break-system-packages = true" >> /root/.pip/pip.conf

RUN pip3 install \
    pwntools \
    angr \
    pycryptodome \
    langgraph \
    langchain \
    langchain-openai \
    langchain-mcp-adapters \
    mcp

WORKDIR /workspace

# Create a non-root user with sudo permissions
RUN useradd -ms /bin/bash ctfuser \
    && echo 'ctfuser ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/ctfuser \
    && chmod 0440 /etc/sudoers.d/ctfuser
USER ctfuser


CMD ["bash", "-lc", "tail -f /dev/null"]
