![alt text]([http://url/to/img.png](https://github.com/martonvoros/leadeable/blob/main/leadable_icon.png))

# Leadable - Sync Facebook Leads with Google Sheets

## Overview
Leadable is a lightweight, user-friendly Python application designed to synchronize Facebook lead data (from lead forms) with Google Sheets. It features a modern, minimalistic GUI built with `customtkinter`, Google OAuth authentication, and customizable synchronization intervals. This tool is ideal for marketers and developers who need to manage and analyze Facebook leads efficiently.

## Features
- **Facebook Integration**: Fetch lead data from Facebook using an access token, ad account ID, and form ID.
- **Google Sheets Sync**: Automatically sync leads to Google Sheets with customizable frequency (e.g., 5 minutes, 1 hour, 1 day).
- **OAuth Authentication**: Secure Google login for accessing Google Sheets.
- **Cross-Platform**: Runs on Windows, macOS, and Linux with Python 3.8+.

## Prerequisites
Before using Leadable, ensure you have the following:

- **Python 3.8 or higher** installed on your system.
- The following Python packages installed (install via `pip`):
  - `customtkinter`
  - `requests`
  - `gspread`
  - `pillow`
  - `google-auth-oauthlib`
  - `webbrowser`
- **Facebook API Access**:
  - A Facebook Access Token with `ads_management` and `leads_retrieval` permissions (obtained via the Graph API Explorer).
  - Your Ad Account ID (e.g., `act_123456789`).
  - Your Lead Form ID (from Facebook Ads Manager or Graph API).
- **Google Cloud Credentials**:
  - A Google Cloud Project with the Google Sheets API and Google Drive API enabled.
  - OAuth 2.0 Client ID and Client Secret (configured in Google Cloud Console).
  - Redirect URI set to `http://localhost:8000/callback`.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/martonvoros/leadable.git
   cd leadable
