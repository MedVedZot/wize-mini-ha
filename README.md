# Wyze Mini HA Integration

<p align="left">
  <a href="https://buymeacoffee.com/MedVedZot">
    <img src="https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&slug=MedVedZot&button_colour=FFDD00&font_colour=000000&font_family=Arial&outline_colour=000000&coffee_colour=ffffff" />
  </a>
</p>
No subscriptions. Just support if you find value.
<br/><br/>

Home Assistant custom integration for Wyze Mini cameras with motion detection via Wyze Cloud API.

![Version](https://img.shields.io/badge/version-1.0.7-blue)
![Home Assistant](https://img.shields.io/badge/HA-2024.1.0%2B-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## Features

- 📊 **Dynamic Camera Discovery** - Automatically discovers available cameras from API
- ☁️ **Cloud API Integration** - Works with Wyze Cloud (direct connection not required)
- 🔐 **Secure Authentication** - Uses your Wyze account credentials and API keys
- 🔄 **Automatic Updates** - Data refreshes every 3 seconds (customizable)
- 📱 **Multiple Cameras** - Choose which cameras to add to Home Assistant
- 📈 **Motion Detection** - Real-time motion sensors with state class for history
- 🎛️ **Customizable** - Add/remove cameras anytime via Options Flow
- 👥 **Multiple Accounts** - Add multiple Wyze accounts simultaneously

## Requirements

- Home Assistant 2024.1.0 or newer
- Wyze account with at least one camera
- Wyze API Key ID and API Key from [Wyze Developer Portal](https://developer.wyzelabs.com/)
- Network access to Wyze Cloud API

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MedVedZot&repository=wize-mini-ha&category=integration)

### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the **three dots menu** → **Custom repositories**
4. Add this repository: `https://github.com/MedVedZot/wize-mini-ha.git`
5. Select category: **Integration**
6. Click **Add**
7. Go to **Integrations** and search for "Wyze Mini HA"
8. Click **Install**
9. Restart Home Assistant