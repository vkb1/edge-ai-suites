# DL Streamer 2026.0.0 Installation Guide

## Prerequisites

Install GPU/NPU drivers using Intel's prerequisite script:

```bash
mkdir -p ~/intel/dlstreamer_gst
cd ~/intel/dlstreamer_gst/
wget -O DLS_install_prerequisites.sh \
  https://raw.githubusercontent.com/open-edge-platform/dlstreamer/main/scripts/DLS_install_prerequisites.sh \
  && chmod +x DLS_install_prerequisites.sh
./DLS_install_prerequisites.sh
```

## Step 1: Set Up APT Repositories

### Ubuntu 22.04

```bash
sudo -E wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB \
  | gpg --dearmor | sudo tee /usr/share/keyrings/intel-gpg-archive-keyring.gpg > /dev/null

sudo -E wget -O- https://apt.repos.intel.com/edgeai/dlstreamer/GPG-PUB-KEY-INTEL-DLS.gpg \
  | sudo tee /usr/share/keyrings/dls-archive-keyring.gpg > /dev/null

echo "deb [signed-by=/usr/share/keyrings/dls-archive-keyring.gpg] \
  https://apt.repos.intel.com/edgeai/dlstreamer/ubuntu22 ubuntu22 main" \
  | sudo tee /etc/apt/sources.list.d/intel-dlstreamer.list

sudo bash -c 'echo "deb [signed-by=/usr/share/keyrings/intel-gpg-archive-keyring.gpg] \
  https://apt.repos.intel.com/openvino ubuntu22 main" \
  | sudo tee /etc/apt/sources.list.d/intel-openvino.list'
```

### Ubuntu 24.04

```bash
sudo -E wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB \
  | gpg --dearmor | sudo tee /usr/share/keyrings/intel-gpg-archive-keyring.gpg > /dev/null

sudo -E wget -O- https://apt.repos.intel.com/edgeai/dlstreamer/GPG-PUB-KEY-INTEL-DLS.gpg \
  | sudo tee /usr/share/keyrings/dls-archive-keyring.gpg > /dev/null

echo "deb [signed-by=/usr/share/keyrings/dls-archive-keyring.gpg] \
  https://apt.repos.intel.com/edgeai/dlstreamer/ubuntu24 ubuntu24 main" \
  | sudo tee /etc/apt/sources.list.d/intel-dlstreamer.list

sudo bash -c 'echo "deb [signed-by=/usr/share/keyrings/intel-gpg-archive-keyring.gpg] \
  https://apt.repos.intel.com/openvino ubuntu24 main" \
  | sudo tee /etc/apt/sources.list.d/intel-openvino.list'
```

> **NOTE:** If you have a different version of OpenVINO installed, remove it first:
> ```bash
> sudo apt remove -y openvino* libopenvino-* python3-openvino*
> sudo apt-get autoremove
> ```

## Step 2: Install DL Streamer

```bash
sudo apt update
sudo apt-get install intel-dlstreamer
```

To install a specific version:

```bash
sudo apt install intel-dlstreamer=2026.0.0
```

## Step 3: Set Environment Variables

Add to `~/.bashrc` or run per session:

```bash
source /opt/intel/dlstreamer/scripts/setup_dls_env.sh
```

## Step 4: Verify Installation

```bash
gst-inspect-1.0 gvadetect
```

You should see the documentation for the `gvadetect` element.

## Step 5: Install Python Dependencies

```bash
pip install -r requirements.txt
```
