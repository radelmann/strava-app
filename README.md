# Strava Activity Metrics

A web application that displays Strava activity metrics for a specific month.

## Setup

1. Create a Strava API application at https://www.strava.com/settings/api
2. Copy your Client ID and Client Secret
3. Create a `.env` file with the following variables:
   ```
   STRAVA_CLIENT_ID=your_client_id
   STRAVA_CLIENT_SECRET=your_client_secret
   ```
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
5. Run the application:
   ```
   python app.py
   ```

## Usage

1. Visit http://localhost:5000 in your browser
2. Click "Connect with Strava" to authorize the application
3. View your activity metrics for April 2025