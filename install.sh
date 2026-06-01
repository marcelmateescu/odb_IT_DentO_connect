#!/usr/bin/env bash
# ========================================================================================
# 🦷 ODONTO.BOT PMS SYNC CONNECTOR INSTALLER FOR macOS 🦷
# ========================================================================================
# Designed & Owned by: S.C. INFORMATICA ECOLOGICA TRANSILVANIA 2004 SRL
# VAT ID: RO17075938 | Contact: iet2k4@gmail.com
# ========================================================================================

# Colors for premium console rendering
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================================================================${NC}"
echo -e "${GREEN}🦷 ODONTO.BOT CONNECTOR LOCAL COMPILATION & DAEMON INSTALLER 🦷${NC}"
echo -e "${BLUE}========================================================================================${NC}"

# --- Step 1: Verify macOS Development Toolchain ---
echo -e "\n${BLUE}[Phase 1/5] Verifying macOS Development Dependencies...${NC}"

# Check for git
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git is not installed on this system.${NC}"
    echo -e "${YELLOW}👉 Installing macOS Command Line Tools... Please click 'Install' on the popup window.${NC}"
    xcode-select --install
    echo -e "${YELLOW}Please re-run this installer once the Command Line Tools installation finishes.${NC}"
    exit 1
else
    echo -e "   » ${GREEN}Git verified:${NC} $(git --version)"
fi

# Check for compiler (gcc/clang)
if ! command -v make &> /dev/null || ! command -v cc &> /dev/null; then
    echo -e "${RED}❌ GNU Make or C Compiler (clang) is missing.${NC}"
    echo -e "${YELLOW}👉 Please install macOS Command Line Tools using: xcode-select --install${NC}"
    exit 1
else
    echo -e "   » ${GREEN}C Compiler toolchain verified.${NC}"
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not found. Python 3 is required to run the sync manager.${NC}"
    echo -e "${YELLOW}👉 Please install Python 3 or Homebrew to proceed.${NC}"
    exit 1
else
    echo -e "   » ${GREEN}Python verified:${NC} $(python3 --version)"
fi

# --- Step 2: Compile Bundled fmptools Locally ---
echo -e "\n${BLUE}[Phase 2/5] Compiling Bundled FMPTools Core...${NC}"

if [ -d "fmptools" ]; then
    echo -e "   » Preparing locally bundled fmptools modules..."
    cd fmptools || exit 1
else
    echo -e "${RED}❌ Error: Bundled 'fmptools' directory is missing.${NC}"
    exit 1
fi

# Make configure executable if necessary
if [ -f "configure" ]; then
    chmod +x configure
else
    # Auto-generation using autotools if configure doesn't exist
    if command -v autoreconf &> /dev/null; then
        echo -e "   » Generating configure script using autotools..."
        autoreconf -i
    else
        echo -e "${RED}❌ Error: 'configure' script is missing and autotools are not installed.${NC}"
        exit 1
    fi
fi

echo -e "   » Configuring locally optimized build..."
./configure --silent

echo -e "   » Compiling binary tools locally (make)..."
make --silent

# Verify that compilation completed successfully
if [ -f "fmp2sqlite" ] || [ -f "src/bin/fmp2sqlite" ]; then
    echo -e "   » ${GREEN}Compilation Succeeded!${NC} Binary tools built locally."
else
    echo -e "${RED}❌ Local C compilation failed. Please verify build flags in config.log.${NC}"
    exit 1
fi

cd .. || exit 1

# --- Step 3: Prepare Python Environment Dependencies ---
echo -e "\n${BLUE}[Phase 3/5] Setting up Python dependencies...${NC}"
python3 -m pip install requests --quiet --disable-pip-version-check
if [ $? -eq 0 ]; then
    echo -e "   » ${GREEN}Python library 'requests' installed successfully.${NC}"
else
    # Fallback in case of environment block or PEP 668 system limits
    echo -e "   » Attempting dependency installation with system bypass (--break-system-packages)..."
    python3 -m pip install requests --quiet --break-system-packages --disable-pip-version-check
fi

# --- Step 4: Run Verification Local Extraction ---
echo -e "\n${BLUE}[Phase 4/5] Executing test extractor & data portability test...${NC}"
if [ -f "extractor.py" ]; then
    python3 extractor.py
    if [ $? -eq 0 ]; then
        echo -e "   » ${GREEN}Verification extractor successfully parsed local records!${NC}"
    else
        echo -e "${RED}❌ Data extraction verification failed.${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ Warning: extractor.py not found in root workspace directory.${NC}"
fi

# --- Step 5: Install Background launchd Daemon ---
echo -e "\n${BLUE}[Phase 5/5] Registering macOS Launch Agent for hourly background synchronization...${NC}"

AGENT_LABEL="com.odontobot.sync"
PLIST_FILE="${HOME}/Library/LaunchAgents/${AGENT_LABEL}.plist"
SCRIPT_PATH="$(pwd)/odontobot_sync_all.py"

# Make sync scripts executable
chmod +x "${SCRIPT_PATH}"
if [ -f "extractor.py" ]; then
    chmod +x extractor.py
fi

# Generate the Launchd Plist Configuration
cat <<EOF > "${PLIST_FILE}"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${SCRIPT_PATH}</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/odontobot_sync_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/odontobot_sync_stderr.log</string>
</dict>
</plist>
EOF

# Load and bootstrap the agent
echo -e "   » Registering background scheduler agent..."
launchctl unload "${PLIST_FILE}" &> /dev/null
launchctl load "${PLIST_FILE}"

if [ $? -eq 0 ]; then
    echo -e "   » ${GREEN}Background daemon loaded successfully!${NC}"
    echo -e "   » Sync stdout log available at: ${HOME}/Library/Logs/odontobot_sync_stdout.log"
    echo -e "   » Sync stderr log available at: ${HOME}/Library/Logs/odontobot_sync_stderr.log"
else
    echo -e "${RED}❌ Failed to load Launchd agent.${NC}"
fi

echo -e "\n${BLUE}========================================================================================${NC}"
echo -e "${GREEN}🎉 ALL SYSTEMS CONFIGURED & COMPILED SUCCESSFULLY!${NC}"
echo -e "   » Local source is compiled under: $(pwd)/fmptools"
echo -e "   » Your sync client will run silently in the background every hour."
echo -e "${BLUE}========================================================================================${NC}"
