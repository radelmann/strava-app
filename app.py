from flask import Flask, render_template, redirect, request, session, url_for, jsonify
import requests
from datetime import datetime, timedelta
import os
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev')

# Strava API credentials
CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
REDIRECT_URI = 'http://127.0.0.1:5000/callback'

# Strava API endpoints
AUTH_URL = 'https://www.strava.com/oauth/authorize'
TOKEN_URL = 'https://www.strava.com/oauth/token'
API_URL = 'https://www.strava.com/api/v3'

# Conversion constants
METERS_TO_MILES = 0.000621371
METERS_TO_FEET = 3.28084

# Activity type mapping for graph.yt
ACTIVITY_TYPE_MAP = {
    "Run": "1",
    "Walk": "2",
    "Hike": "3",
    "Bike": "4",
    "Swim": "5",
    "Kayak": "6",
    "Stand Up Paddle": "7",
    "Row": "8",
    "Workout": "9",
    "Yoga": "10",
    "Other": "11"
}

# Activity type variations for flexible matching
ACTIVITY_VARIATIONS = {
    "Run": ["run", "running", "jog", "jogging"],
    "Walk": ["walk", "walking", "stroll"],
    "Hike": ["hike", "hiking", "trail", "mountain"],
    "Bike": ["bike", "biking", "cycling", "cycle", "ride"],
    "Swim": ["swim", "swimming"],
    "Kayak": ["kayak", "kayaking"],
    "Stand Up Paddle": ["paddle", "sup", "stand up paddle"],
    "Row": ["row", "rowing"],
    "Workout": ["workout", "strength", "weight", "gym", "crossfit"],
    "Yoga": ["yoga", "stretch", "meditation"],
    "Other": ["other"]
}

def format_time(minutes):
    """Convert minutes to HH:MM format.

    Args:
        minutes (float): Total minutes to format

    Returns:
        str: Time formatted as HH:MM
    """
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours:02d}:{mins:02d}"

def get_activity_type(activity_name):
    """Get the activity type code based on partial matches in the activity name.

    Args:
        activity_name (str): The name of the activity to match

    Returns:
        str: The corresponding activity type code, or "11" for Other if no match found
    """
    # Convert activity name to lowercase for case-insensitive matching
    activity_name = activity_name.lower()
    print(f"\n=== Activity Type Matching ===")
    print(f"Activity name: {activity_name}")

    # Check for matches in the activity name
    for activity_type, variations in ACTIVITY_VARIATIONS.items():
        print(f"\nChecking {activity_type} variations:")
        for variation in variations:
            print(f"  - Checking '{variation}' in '{activity_name}'")
            if variation in activity_name:
                print(f"  ✓ Match found! Using type code: {ACTIVITY_TYPE_MAP[activity_type]}")
                return ACTIVITY_TYPE_MAP[activity_type]
            else:
                print(f"  ✗ No match")

    print("\nNo matches found, defaulting to 'Other' (11)")
    return "11"

def get_strava_auth_url():
    """Generate the Strava OAuth authorization URL.

    Returns:
        str: The complete authorization URL with all required parameters
    """
    return (
        f"https://www.strava.com/oauth/authorize?"
        f"client_id={os.getenv('STRAVA_CLIENT_ID')}&"
        f"redirect_uri={url_for('strava_callback', _external=True)}&"
        f"response_type=code&"
        f"scope=activity:read_all,profile:read_all"
    )

def get_strava_access_token(code: str) -> dict:
    """
    Exchange authorization code for access token from Strava API.

    Args:
        code (str): Authorization code received from Strava

    Returns:
        dict: Token data containing access_token and other fields

    Raises:
        ValueError: If token exchange fails or response is invalid
    """
    try:
        # Print the code for debugging
        print(f"Exchanging code: {code}")

        # Make request to Strava token endpoint
        response = requests.post(
            'https://www.strava.com/oauth/token',
            data={
                'client_id': os.getenv('STRAVA_CLIENT_ID'),
                'client_secret': os.getenv('STRAVA_CLIENT_SECRET'),
                'code': code,
                'grant_type': 'authorization_code'
            }
        )

        # Print the full response for debugging
        print(f"Token response status: {response.status_code}")
        print(f"Token response body: {response.text}")

        # Check if request was successful
        response.raise_for_status()

        # Parse response
        token_data = response.json()

        # Validate token data
        if not token_data or 'access_token' not in token_data:
            print(f"Invalid token response: {token_data}")
            raise ValueError("Invalid token response from Strava API")

        return token_data

    except requests.exceptions.RequestException as e:
        print(f"Error exchanging code for token: {str(e)}")
        raise ValueError(f"Failed to exchange code for token: {str(e)}")
    except ValueError as e:
        print(f"Error processing token response: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error in get_strava_access_token: {str(e)}")
        raise ValueError(f"Unexpected error: {str(e)}")

def get_strava_activities(access_token: str, start_date: datetime, end_date: datetime) -> list:
    """
    Fetch activities from Strava API for a given date range.

    Args:
        access_token (str): Strava API access token
        start_date (datetime): Start of date range
        end_date (datetime): End of date range

    Returns:
        list: List of activities with detailed data
    """
    try:
        # First, get the list of activities
        response = requests.get(
            'https://www.strava.com/api/v3/athlete/activities',
            headers={'Authorization': f'Bearer {access_token}'},
            params={
                'after': int(start_date.timestamp()),
                'before': int(end_date.timestamp()),
                'per_page': 100  # Maximum allowed by Strava
            }
        )
        response.raise_for_status()
        activities = response.json()

        # Fetch detailed data for each activity
        detailed_activities = []
        for activity in activities:
            try:
                # Get detailed activity data
                detail_response = requests.get(
                    f'https://www.strava.com/api/v3/activities/{activity["id"]}',
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                detail_response.raise_for_status()
                detailed_activity = detail_response.json()
                detailed_activities.append(detailed_activity)

                # Print debug info for calories
                print(f"\nActivity: {detailed_activity.get('name')}")
                print(f"Calories from detailed data: {detailed_activity.get('calories')}")

            except requests.exceptions.RequestException as e:
                print(f"Error fetching details for activity {activity.get('id')}: {str(e)}")
                # Use the basic activity data if detailed fetch fails
                detailed_activities.append(activity)

        return detailed_activities

    except requests.exceptions.RequestException as e:
        print(f"Error fetching activities: {str(e)}")
        raise ValueError(f"Failed to fetch activities: {str(e)}")
    except Exception as e:
        print(f"Unexpected error in get_strava_activities: {str(e)}")
        raise ValueError(f"Unexpected error: {str(e)}")

def process_activity(activity: dict) -> dict:
    """
    Process a single Strava activity and extract relevant metrics.

    Args:
        activity (dict): Raw activity data from Strava API

    Returns:
        dict: Processed activity data with formatted metrics
    """
    try:
        # Print raw activity data for debugging
        print(f"\nProcessing activity: {activity.get('name')}")
        print(f"Raw calories: {activity.get('calories')}")
        print(f"Raw activity data: {json.dumps(activity, indent=2)}")

        # Calculate calories if not provided
        calories = activity.get('calories')
        if calories is None and activity.get('has_heartrate'):
            # Simple calorie estimation based on heart rate and duration
            # Formula: calories = (average_heartrate * duration_in_hours * 3.5) / 4.184
            duration_hours = activity.get('moving_time', 0) / 3600  # Convert seconds to hours
            avg_heartrate = activity.get('average_heartrate', 0)
            if avg_heartrate > 0:
                calories = int((avg_heartrate * duration_hours * 3.5) / 4.184)
                print(f"Calculated estimated calories: {calories}")

        # Extract and format activity data
        processed = {
            'id': activity.get('id'),
            'name': activity.get('name'),
            'date': activity.get('start_date_local', '').split('T')[0],
            'distance': activity.get('distance', 0) * 0.000621371,  # Convert meters to miles
            'calories': calories if calories is not None else 'N/A',
            'elevation': activity.get('total_elevation_gain', 0) * 3.28084,  # Convert meters to feet
            'time': format_time(activity.get('moving_time', 0))
        }

        # Print processed data for debugging
        print(f"Processed calories: {processed['calories']}")
        print(f"Processed activity data: {json.dumps(processed, indent=2)}")

        return processed

    except Exception as e:
        print(f"Error processing activity: {str(e)}")
        print(f"Activity data: {json.dumps(activity, indent=2)}")
        raise

def get_graph_yt_headers():
    """Get the headers required for graph.yt API requests.

    Returns:
        dict: Headers for graph.yt API requests
    """
    return {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded',
        'cookie': f'challenge={os.getenv("GRAPH_YT_CHALLENGE")}; PHPSESSID={os.getenv("GRAPH_YT_PHPSESSID")}',
        'origin': 'https://graph.yt',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'referer': 'https://graph.yt/add_activity.php',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }

@app.route('/')
def index():
    """Render the index page with Strava authorization link."""
    return render_template('index.html', auth_url=get_strava_auth_url())

@app.route('/strava_callback')
def strava_callback():
    """
    Handle Strava OAuth callback and store access token in session.
    """
    try:
        # Get authorization code from query parameters
        code = request.args.get('code')
        if not code:
            return redirect(url_for('index', error='No authorization code received'))

        # Exchange code for access token
        token_data = get_strava_access_token(code)

        # Store token in session
        session['access_token'] = token_data['access_token']
        session['athlete_id'] = token_data['athlete']['id']

        # Redirect to activities page
        return redirect(url_for('activities'))

    except ValueError as e:
        print(f"Error in strava_callback: {str(e)}")
        return redirect(url_for('index', error=str(e)))
    except Exception as e:
        print(f"Unexpected error in strava_callback: {str(e)}")
        return redirect(url_for('index', error=f"Unexpected error: {str(e)}"))

@app.route('/activities')
def activities():
    """Display the user's activities for April 2025."""
    if 'access_token' not in session:
        return redirect(url_for('index'))

    # Set date range for April 2025
    start_date = datetime(2025, 4, 1)
    end_date = datetime(2025, 4, 30)

    # Fetch activities from Strava
    activities_data = get_strava_activities(session['access_token'], start_date, end_date)

    # Process activities
    processed_activities = []
    totals = {
        'distance': 0,
        'calories': 0,
        'elevation': 0,
        'time': 0
    }

    for activity in activities_data:
        # Parse the activity date
        activity_date = datetime.strptime(activity['start_date_local'].split('T')[0], '%Y-%m-%d')

        # Only include activities from April 2025
        if start_date <= activity_date <= end_date:
            processed_activity = process_activity(activity)
            processed_activities.append(processed_activity)

            # Update totals
            if processed_activity['calories'] != 'N/A':
                totals['calories'] += processed_activity['calories']
            totals['distance'] += processed_activity['distance']
            totals['elevation'] += processed_activity['elevation']

            # Parse time string back to minutes for total
            hours, minutes = map(int, processed_activity['time'].split(':'))
            totals['time'] += hours * 60 + minutes

    # Format total time
    totals['time'] = format_time(totals['time'])

    return render_template(
        'activities.html',
        activities=processed_activities,
        totals=totals
    )

@app.route('/proxy/add_activity', methods=['POST'])
def proxy_add_activity():
    """Proxy endpoint for adding activities to graph.yt."""
    try:
        # Get the form data from the request
        data = request.form
        print("\n=== Request to graph.yt ===")
        print("Form data:", dict(data))

        # Get the activity type from the mapping using partial match
        activity_type = get_activity_type(data['type'])
        print(f"Activity name: {data['type']}, Mapped type: {activity_type}")

        # Forward the request to graph.yt
        response = requests.post(
            'https://graph.yt/add_activity.php',
            headers=get_graph_yt_headers(),
            data={
                'type': activity_type,
                'date': data['date'],
                'distance': data['distance'],
                'distance_unit': 'miles',
                'calories': data['calories']
            }
        )

        print("\n=== Response from graph.yt ===")
        print("Status code:", response.status_code)
        print("Response headers:", dict(response.headers))
        print("Response content:", response.text[:500])  # Print first 500 chars of response

        # Check if the response is successful and contains the success message
        if response.status_code == 200 and "Activity successfully added to your activities!" in response.text:
            # Return a JSON response indicating success
            return jsonify({'status': 'success', 'message': 'Activity added successfully'})
        else:
            # Return a JSON response indicating failure
            return jsonify({'status': 'error', 'message': 'Failed to add activity. Unexpected response from server.'}), 400
    except Exception as e:
        print("\n=== Error in proxy endpoint ===")
        print("Error:", str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)