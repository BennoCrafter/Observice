# install-linux.sh
#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

OS_TYPE=$(uname -s)

git pull

echo -e "${GREEN}🚀 Starting Garage Cam Installation...${RESET}"

echo -e "${GREEN}🔍 Detected OS: ${OS_TYPE} ${RESET}"
if [ "$OS_TYPE" != "Linux" ]; then
    if [ "$OS_TYPE" == "Darwin" ]; then
        echo -e "${RED}🍎 macOS detected. Please run the install-darwin.sh script instead.${RESET}"
        exit
    else
        echo -e "${RED}🚨 Unsupported OS detected.${RESET}"
        exit
    fi
fi

# Install Docker if not installed
if ! command -v docker &> /dev/null; then
    echo -e "${GREEN}🛠 Installing Docker...${RESET}"
    curl -fsSL https://get.docker.com | sudo bash
    sudo usermod -aG docker $USER
else
    echo -e "${GREEN}✅ Docker is already installed.${RESET}"
fi

# Enable Docker on boot
sudo systemctl enable docker
sudo systemctl start docker

# Install Docker Compose if not installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}🛠 Installing Docker Compose...${RESET}"
    sudo apt-get install -y docker-compose
else
    echo -e "${GREEN}✅ Docker Compose is already installed.${RESET}"
fi

echo -e "${GREEN}🐳 Building and starting Observice container...${RESET}"
docker compose build
docker compose up -d

echo -e "${GREEN}✅ Installation Complete!${RESET}"
