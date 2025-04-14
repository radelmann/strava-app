from flask import Flask, render_template, redirect, request, session, url_for, jsonify
import requests
from datetime import datetime
import os
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

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

def format_time(minutes):
    """Convert minutes to hh:mm format"""
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours:02d}:{mins:02d}"

def get_activity_type(activity_name):
    """Get the activity type code based on partial matches in the activity name"""
    # Convert activity name to lowercase for case-insensitive matching
    activity_name = activity_name.lower()
    print(f"\n=== Activity Type Matching ===")
    print(f"Activity name: {activity_name}")

    # Define variations of activity types
    activity_variations = {
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

    # Check for matches in the activity name
    for activity_type, variations in activity_variations.items():
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

@app.route('/')
def index():
    if 'access_token' not in session:
        # Request additional scopes that might be needed for calorie data
        auth_url = f"{AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=activity:read_all,profile:read_all"
        return render_template('index.html', auth_url=auth_url)

    return redirect(url_for('activities'))

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return redirect(url_for('index'))

    # Exchange authorization code for access token
    token_response = requests.post(TOKEN_URL, data={
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    })

    if token_response.status_code == 200:
        token_data = token_response.json()
        session['access_token'] = token_data['access_token']
        return redirect(url_for('activities'))

    return "Error getting access token", 400

@app.route('/activity/<int:activity_id>')
def get_activity(activity_id):
    """Get detailed information about a specific activity"""
    if 'access_token' not in session:
        return redirect(url_for('index'))

    headers = {'Authorization': f'Bearer {session["access_token"]}'}
    activity_response = requests.get(
        f"{API_URL}/activities/{activity_id}",
        headers=headers
    )

    if activity_response.status_code != 200:
        return f"Error fetching activity {activity_id}", 400

    activity = activity_response.json()
    return jsonify(activity)

@app.route('/activities')
def activities():
    if 'access_token' not in session:
        return redirect(url_for('index'))

    # Get activities for April 2025
    start_date = datetime(2025, 4, 1).timestamp()
    end_date = datetime(2025, 5, 1).timestamp()

    headers = {'Authorization': f'Bearer {session["access_token"]}'}
    activities_response = requests.get(
        f"{API_URL}/athlete/activities",
        headers=headers,
        params={'after': start_date, 'before': end_date}
    )

    if activities_response.status_code != 200:
        return "Error fetching activities", 400

    activities = activities_response.json()

    # Debug: Print the first activity to see its structure
    if activities:
        print("\nFirst activity data from list endpoint:")
        print(json.dumps(activities[0], indent=2))

        # Get detailed data for the first activity to compare
        activity_id = activities[0]['id']
        headers = {'Authorization': f'Bearer {session["access_token"]}'}
        detailed_response = requests.get(
            f"{API_URL}/activities/{activity_id}",
            headers=headers
        )

        if detailed_response.status_code == 200:
            detailed_activity = detailed_response.json()
            print("\nDetailed activity data for the same activity:")
            print(json.dumps(detailed_activity, indent=2))

            # Compare calories between list and detailed endpoints
            list_calories = activities[0].get('calories')
            detailed_calories = detailed_activity.get('calories')
            print(f"\nCalories from list endpoint: {list_calories}")
            print(f"Calories from detailed endpoint: {detailed_calories}")

    # Process activities data
    processed_activities = []
    totals = {
        'distance': 0,
        'calories': 0,
        'elevation_gain': 0,
        'moving_time': 0
    }

    has_calories_data = False

    for activity in activities:
        # Parse the ISO format date string, removing the 'Z' timezone indicator
        date_str = activity['start_date'].replace('Z', '+00:00')
        minutes = activity['moving_time'] / 60

        # Debug: Print raw calorie data
        print(f"\nProcessing activity: {activity['name']}")
        print(f"Raw calories value: {activity.get('calories')}")
        print(f"Calories type: {type(activity.get('calories'))}")

        # Get calories directly from the 'calories' field
        calories = activity.get('calories')

        # If calories is None or 0, check if it's available in other fields
        if calories is None or calories == 0:
            print("Calories not found in 'calories' field, checking alternatives...")
            # Check for calories in different possible field names
            possible_calorie_fields = ['total_calories', 'calorie', 'total_calorie', 'kilo_calories', 'kilocalories']
            for field in possible_calorie_fields:
                if field in activity:
                    print(f"Found field '{field}' with value: {activity[field]}")
                    if activity[field] is not None and activity[field] > 0:
                        calories = activity[field]
                        print(f"Using calories from '{field}': {calories}")
                        break

            # If still no calories, try to fetch detailed activity data
            if calories is None or calories == 0:
                print("No calories found in list endpoint, trying to fetch detailed data...")
                activity_id = activity['id']
                headers = {'Authorization': f'Bearer {session["access_token"]}'}
                detailed_response = requests.get(
                    f"{API_URL}/activities/{activity_id}",
                    headers=headers
                )

                if detailed_response.status_code == 200:
                    detailed_activity = detailed_response.json()
                    detailed_calories = detailed_activity.get('calories')
                    print(f"Calories from detailed endpoint: {detailed_calories}")

                    if detailed_calories is not None and detailed_calories > 0:
                        calories = detailed_calories
                        print(f"Using calories from detailed endpoint: {calories}")

        if calories is not None and calories > 0:
            print(f"Final calories value: {calories}")
            has_calories_data = True
            totals['calories'] += calories
        else:
            print("No valid calories data found")

        processed_activity = {
            'id': activity['id'],
            'name': activity['name'],
            'date': datetime.fromisoformat(date_str).strftime('%Y-%m-%d'),
            'distance': round(activity['distance'] * METERS_TO_MILES, 2),  # Convert to miles
            'calories': calories if calories is not None and calories > 0 else "N/A",
            'elevation_gain': round(activity['total_elevation_gain'] * METERS_TO_FEET),  # Convert to feet
            'moving_time': format_time(minutes)  # Format as hh:mm
        }

        processed_activities.append(processed_activity)

        # Update totals
        totals['distance'] += processed_activity['distance']
        totals['elevation_gain'] += processed_activity['elevation_gain']
        totals['moving_time'] += minutes  # Keep as minutes for total calculation

    # Format the total time
    totals['moving_time'] = format_time(totals['moving_time'])

    # If no calories data is available, set the total to "N/A"
    if not has_calories_data:
        totals['calories'] = "N/A"

    return render_template('activities.html',
                         activities=processed_activities,
                         totals=totals)

@app.route('/proxy/add_activity', methods=['POST'])
def proxy_add_activity():
    try:
        # Get the form data from the request
        data = request.form
        print("\n=== Request to graph.yt ===")
        print("Form data:", dict(data))

        # Get the activity type from the mapping using partial match
        activity_type = get_activity_type(data['type'])
        print(f"Activity name: {data['type']}, Mapped type: {activity_type}")

        # Construct the cookie header from environment variables
        cookie_header = f'challenge={os.getenv("GRAPH_YT_CHALLENGE")}; PHPSESSID={os.getenv("GRAPH_YT_PHPSESSID")}'

        # Forward the request to graph.yt
        response = requests.post(
            'https://graph.yt/add_activity.php',
            headers={
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'en-US,en;q=0.9',
                'cache-control': 'no-cache',
                'content-type': 'application/x-www-form-urlencoded',
                'cookie': cookie_header,
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
            },
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