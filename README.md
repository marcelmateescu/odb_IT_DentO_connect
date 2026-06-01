# 🦷 odb_IT_DentO_connect

[![License: BSL 1.1](https://img.shields.io/badge/License-BSL_1.1-blue.svg)](file:///Users/mateescu_m/Desktop/RuntimeDento_6.9.8/LEGAL.md)
[![BSL Change Date: June 1, 2040](https://img.shields.io/badge/Change_Date-June_1,_2040-orange.svg)](file:///Users/mateescu_m/Desktop/RuntimeDento_6.9.8/LEGAL.md)
[![Language Support: EN | IT | RO](https://img.shields.io/badge/Languages-EN%20%7C%20IT%20%7C%20RO-green.svg)](file:///Users/mateescu_m/Desktop/RuntimeDento_6.9.8/LEGAL.html)
[![Platform support: macOS & Windows](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-lightgrey.svg)](file:///Users/mateescu_m/Desktop/RuntimeDento_6.9.8/install.sh)

An enterprise-grade, secure offline synchronization bridge designed to extract clinical records from local, de-obfuscated `DentO` FileMaker databases and synchronize them in real time with the **[odonto.bot](https://odonto.bot)** automation platform.

This utility serves as the official client-side sync connector connecting local clinic operations directly into the central cloud engine. For technical API schemas, tokens, and developer configuration parameters, please reference the **[Odonto.bot Developer Portal](https://odontobot-data-automation.web.app/api-access)**.

---

## 🏛️ EU Interoperability Protection & Compliance

This connector is engineered and operated in strict compliance with the **EU Software Directive (Directive 2009/24/EC, Article 6 - Decompilation)** and its Italian national transposition (**Legge 22 aprile 1941 n. 633, Articolo 64-quater**).

*   **Right to Interoperability**: EU law explicitly guarantees software licensees the right to reverse-engineer and parse proprietary file structures (`.fmp12` / `.fmpur`) and de-obfuscate simple static mask patterns (such as XOR `0x5A`) *without* Claris/Apple consent, provided it is done solely to achieve **interoperability with an independently created computer program** (the `odonto.bot` API).
*   **100% Binary Isolation**: The sync connector operates entirely in userland, engaging through standard HTTPS endpoints. It does not copy, modify, or distribute any proprietary FileMaker engine code, libraries, or system binaries.

---

## 📂 Custom Attribution & C-Level Parser Core

The binary file structure parser modules utilized by this connector are built atop the open-source **[fmptools](https://github.com/evanmiller/fmptools)** library originally designed by **Evan Miller** under the permissive **MIT License**.

All subsequent modifications, SQLite relational translators, Python extraction pipelines, and automated multi-entity synchronization engines are designed and owned by **S.C. INFORMATICA ECOLOGICA TRANSILVANIA 2004 SRL**.

---

## 🚀 Installation & Background Deployment Guides

This connector supports silent, automated background synchronization for both **macOS** and **Windows** environments.

### 🍎 1. macOS Deployment (Local C Compiler Build & Launchd Agent)
The macOS installer uses a compiler-based setup to automatically configure and compile the custom de-obfuscation parser tools locally.

#### 🦷 Dentist-Friendly macOS Step-by-Step Tutorial (No "Homebrew" or technical skills required!)
You do **not** need to be a developer or have any package managers (like Homebrew) installed. macOS has everything built-in to install this for you automatically. Just follow these simple steps:

1.  **Open Terminal**: Press `Cmd + Space` on your keyboard (Spotlight Search), type `Terminal`, and press `Enter`.
2.  **Navigate to this Folder**: Type `cd ` (with a trailing space) in the Terminal window, then **drag and drop** this folder from Finder directly into your Terminal, and press `Enter`.
3.  **Run the Installer**: Copy and paste the following command into your Terminal, then press `Enter`:
    ```bash
    chmod +x install.sh && ./install.sh
    ```
4.  **Click "Install" on the macOS Popup**: 
    *   If your Mac doesn't have command-line compiler tools set up, macOS will automatically display a popup window saying: *“The 'git' command requires the command line developer tools. Would you like to install the tools now?”*
    *   Simply click **Install** and agree to the license terms. macOS will download and install the tools automatically in the background (takes a few minutes).
5.  **Re-run the Installer**: Once the macOS tools installation finishes, go back to your Terminal and run the installer script one final time:
    ```bash
    ./install.sh
    ```
    *   *That's it!* The compiler will build the secure parser natively for your Mac (whether Intel or Apple Silicon M1/M2/M3/M4), configure Python, and set up your synchronization daemon to run silently in the background every hour.

*   *View macOS Service Logs*:
    *   **Stdout logs**: `tail -f ~/Library/Logs/odontobot_sync_stdout.log`
    *   **Stderr logs**: `tail -f ~/Library/Logs/odontobot_sync_stderr.log`

---

###  Windows Deployment (Task Scheduler Setup)
The Windows deployment handles configuration, environment validation, and schedules background tasks natively.

1.  Ensure you have **[Python 3.x](https://www.python.org/downloads/)** installed and added to your system PATH during installation.
2.  Double-click or run the Windows batch script in an Administrator command prompt:
    ```cmd
    install_odb_dento.cmd
    ```
3.  **Daemon Integration**: The batch script automatically verifies the Python environment, setups required modules (`requests`), and registers a persistent background task in the **Windows Task Scheduler** named `OdontoBotSync` which executes the client pipeline silently every hour.

---

## 🛡️ Business Source License 1.1 (BSL 1.1) Terms

This sync connector is distributed under the source-available **Business Source License 1.1 (BSL 1.1)** owned by S.C. INFORMATICA ECOLOGICA TRANSILVANIA 2004 SRL.

*   **🟢 Licensed Use**: 
    *   **Odonto.bot Connection**: Licensed use is fully and PRIMARILY granted to establish secure database connection and offline synchronization with the **Odonto.bot** automation platform (of course!).
    *   **Interoperability & Testing**: Anyone is fully permitted to copy, view, compile, test, and use the source code for personal, internal, non-commercial clinical, or interoperability testing purposes.
*   **🔴 Explicit Competition & SaaS Restrictions**: 
    *   **No Platform Competition**: You are strictly forbidden from using this source code or its compiled binaries to build, distribute, or support any system or platform that competes directly or indirectly with **Odonto.bot**.
    *   **No SaaS or PMS Bundling**: You are strictly prohibited from embedding, bundling, or packaging this connector into any commercial dental Practice Management System (PMS), SaaS platform, or paid connector bundle without express written consent.
*   **📅 Change Date**: On **June 1, 2040**, the restrictions above will expire, and this repository will automatically transition to be licensed under the standard open-source **GNU General Public License v3 (GPLv3)**.

### 🏛️ Interactive Licensing Portal & Live BSL 1.1 Notice
*   For a formal standard legal notice, read the **[LEGAL.md](file:///Users/mateescu_m/Desktop/RuntimeDento_6.9.8/LEGAL.md)** file.
*   **Live Interactive Legal Portal**: The project features a premium, glassmorphic legal portal with active multilingual selectors (**IT/EN/RO**), hosted live via GitHub Pages at:
    👉 **[marcelmateescu.github.io/odb_IT_DentO_connect/LEGAL.html](https://marcelmateescu.github.io/odb_IT_DentO_connect/LEGAL.html)**
*   You can also view the local file template in **[LEGAL.html](file:///Users/mateescu_m/Desktop/RuntimeDento_6.9.8/LEGAL.html)**.

> [!TIP]  
> **Branded Web Hosting Option**:  
> In addition to GitHub Pages, you can also copy `LEGAL.html` to your central Firebase Hosting bucket for the main application to serve it natively at `https://odontobot-data-automation.web.app/legal.html`.
