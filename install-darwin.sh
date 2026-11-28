# install-darwin.sh
#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

OS_TYPE=$(uname -s)

git pull

echo "${GREEN}🚀 Starting Observice Installation...${RESET}"

echo "${GREEN}🔍 Detected OS: ${OS_TYPE} ${RESET}"
if [ "$OS_TYPE" != "Darwin" ]; then
    if [ "$OS_TYPE" == "Linux" ]; then
        echo "${RED}🍎 Linux detected. Please run the install-linux.sh script instead.${RESET}"
        exit
    else
        echo "${RED}🚨 Unsupported OS detected.${RESET}"
        exit
    fi
fi

# Install Homebrew if missing
if ! command -v brew &> /dev/null; then
    echo "${RED}🛠 Please install Homebrew first.${RESET}"
    exit
fi

# Install Docker Desktop for macOS
if ! command -v docker &> /dev/null; then
    echo "${GREEN}🛠 Installing Docker Desktop...${RESET}"
    brew install --cask docker
    echo "${RED}⚠️ Please open Docker Desktop manually to complete installation.${RESET}"
else
    echo "${GREEN}✅ Docker is already installed.${RESET}"
fi

# Start Docker if not running
if ! pgrep -x "Docker" > /dev/null; then
    echo "${GREEN}🔄 Starting Docker...${NC}"
    open -a Docker
    echo "${GREEN}⚠️ Please wait for Docker to fully start before continuing.${NC}"
fi

echo "${GREEN}🐳 Building and starting Observice container...${NC}"
docker compose build
docker compose up -d

echo "${GREEN}✅ Installation Complete!${NC}"
