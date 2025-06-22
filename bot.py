from flask import Flask, render_template_string, request, redirect, url_for, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests, os
from functools import wraps
from dotenv import load_dotenv
from datetime import datetime

# .env ফাইল থেকে এনভায়রনমেন্ট ভেরিয়েবল লোড করুন
load_dotenv()

app = Flask(__name__)

# Environment variables
MONGO_URI = os.getenv("MONGO_URI")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
AD_PROVIDER_API_KEY = os.getenv("AD_PROVIDER_API_KEY")

# Admin credentials
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")

# Database connection
try:
    client = MongoClient(MONGO_URI)
    db = client["movie_db"]
    movies = db["movies"]
    ads = db["ads"]
    ad_providers = db["ad_providers"]  # New collection for ad providers
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}. Exiting.")
    exit(1)

# TMDb Genre Map
TMDb_Genre_Map = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    99: "Documentary", 18: "Drama", 10402: "Music", 9648: "Mystery",
    10749: "Romance", 878: "Science Fiction", 10770: "TV Movie", 53: "Thriller",
    10752: "War", 37: "Western", 10751: "Family", 14: "Fantasy", 36: "History"
}

# --- Authentication functions ---
def check_auth(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated
# --- Authentication functions end ---

# --- Ad system functions ---
def fetch_ad_code(provider_name, ad_format, position):
    """Fetch ad code from provider's API"""
    provider = ad_providers.find_one({"name": provider_name, "is_active": True})
    if not provider:
        return None
    
    try:
        headers = {"Authorization": f"Bearer {provider['api_key']}"}
        params = {
            "format": ad_format,
            "position": position,
            "width": get_width_for_position(position)
        }
        
        response = requests.get(
            provider["api_endpoint"],
            headers=headers,
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json().get("ad_code")
    
    except Exception as e:
        print(f"Error fetching ad from {provider_name}: {e}")
    
    return None

def get_width_for_position(position):
    """Get appropriate ad width based on position"""
    return {
        "header": 728,
        "middle": 300,
        "footer": 320,
        "sidebar": 160
    }.get(position, 300)

def get_automated_ad(position, ad_format):
    """Get ad code from active providers based on priority"""
    active_providers = list(ad_providers.find({"is_active": True}).sort("priority", 1))
    
    for provider in active_providers:
        ad_code = fetch_ad_code(provider["name"], ad_format, position)
        if ad_code:
            return {
                "type": "automated",
                "ad_code": ad_code,
                "position": position
            }
    
    # Fallback to our own ads if no provider has ads
    return get_fallback_ad(position, ad_format)

def get_fallback_ad(position, ad_format):
    """Get fallback ad from our own system"""
    try:
        ad = ads.find_one({
            "position": position,
            "type": ad_format,
            "is_active": True
        })
        if ad:
            ad['_id'] = str(ad['_id'])
            return ad
        return None
    except:
        return None

def get_active_ads(position):
    """Get ads - automated first, then fallback to our own"""
    ads_list = []
    
    # Try to get automated ads
    automated_banner = get_automated_ad(position, "banner")
    if automated_banner:
        ads_list.append(automated_banner)
    
    automated_native = get_automated_ad(position, "native")
    if automated_native:
        ads_list.append(automated_native)
    
    # If no automated ads, get our own
    if not ads_list:
        own_ads = ads.find({
            "position": position,
            "is_active": True
        }).sort('created_at', -1).limit(3)
        
        for ad in own_ads:
            ad['_id'] = str(ad['_id'])
            ads_list.append(ad)
    
    return ads_list
# --- Ad system functions end ---

# --- START OF index_html TEMPLATE ---
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>MovieZone - Your Entertainment Hub</title>
<style>
  /* Reset & basics */
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  body {
    background: #121212; /* Dark background */
    color: #eee;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    -webkit-tap-highlight-color: transparent;
  }
  a { text-decoration: none; color: inherit; }
  a:hover { color: #1db954; } /* Adjusted hover color */
  
  /* Header Styles */
  header {
    position: sticky;
    top: 0; left: 0; right: 0;
    background: #181818;
    padding: 10px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    z-index: 100;
    box-shadow: 0 2px 5px rgba(0,0,0,0.7);
  }
  header h1 {
    margin: 0;
    font-weight: 700;
    font-size: 24px;
    background: linear-gradient(270deg, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3); /* RGB gradient for title */
    background-size: 400% 400%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: gradientShift 10s ease infinite;
  }

  @keyframes gradientShift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }

  form {
    flex-grow: 1;
    margin-left: 20px; /* Space between title and search */
  }
  input[type="search"] {
    width: 100%;
    max-width: 400px;
    padding: 8px 12px;
    border-radius: 30px;
    border: none;
    font-size: 16px;
    outline: none;
    background: #fff;
    color: #333;
  }
  input[type="search"]::placeholder {
      color: #999;
  }
  
  /* Ad Container Styles */
  .ad-container {
    width: 100%;
    text-align: center;
    margin: 15px 0;
    padding: 10px;
    background: #1f1f1f;
    border-radius: 8px;
    overflow: hidden;
  }
  
  .ad-banner {
    display: block;
    margin: 0 auto;
    max-width: 100%;
    max-height: 90px;
    border-radius: 5px;
  }
  
  .native-ad {
    display: flex;
    align-items: center;
    background: #282828;
    border-radius: 8px;
    padding: 10px;
    text-align: left;
  }
  
  .native-ad img {
    width: 80px;
    height: 80px;
    object-fit: cover;
    border-radius: 5px;
    margin-right: 15px;
  }
  
  .native-ad-content {
    flex-grow: 1;
  }
  
  .native-ad h4 {
    font-size: 16px;
    margin-bottom: 5px;
    color: #1db954;
  }
  
  .native-ad p {
    font-size: 14px;
    color: #ccc;
  }

  /* Main Content Area */
  main {
    max-width: 1200px; /* Max width for content */
    margin: 20px auto;
    padding: 0 15px;
    padding-bottom: 70px; /* Space for bottom nav */
  }

  /* Category Section Header */
  .category-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding: 10px 0;
      border-bottom: 2px solid #333; /* A subtle separator */
  }
  .category-header h2 {
      font-size: 22px;
      font-weight: 700;
      color: #e44d26; /* Orange/Red for category titles */
      margin: 0;
  }
  .category-header .see-all-btn {
      background: #333;
      color: #eee;
      padding: 8px 15px;
      border-radius: 20px;
      font-size: 14px;
      text-transform: uppercase;
      transition: background 0.2s ease;
  }
  .category-header .see-all-btn:hover {
      background: #555;
      color: #1db954;
  }


  /* Movie Grid and Card Styles */
  .grid {
    display: grid;
    grid-auto-flow: column; /* Changed to flow horizontally */
    grid-auto-columns: minmax(180px, 1fr); /* Set column width for horizontal flow */
    gap: 20px;
    margin-bottom: 40px; /* Space after each grid section */
    overflow-x: auto; /* Enable horizontal scrolling */
    -webkit-overflow-scrolling: touch; /* Smooth scrolling on iOS */
    scroll-snap-type: x mandatory; /* Snap to items */
    padding-bottom: 10px; /* Add padding for scrollbar */
  }

  /* New style for vertical grid layout (for "See All" pages) */
  .vertical-grid {
    grid-auto-flow: row; /* Change to flow vertically */
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); /* 3-5 columns on desktop */
    overflow-x: visible; /* Disable horizontal scrolling */
    -webkit-overflow-scrolling: auto; /* Revert scrolling */
    scroll-snap-type: none; /* Disable snapping */
    padding-bottom: 0; /* No extra padding for scrollbar */
  }

  /* Hide scrollbar for Chrome, Safari and Opera */
  .grid::-webkit-scrollbar {
    display: none;
  }
  /* Hide scrollbar for IE, Edge and Firefox */
  .grid {
    -ms-overflow-style: none;  /* IE and Edge */
    scrollbar-width: none;  /* Firefox */
  }

  .movie-card {
    background: #181818; /* Dark card background */
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 0 8px rgba(0,0,0,0.6);
    transition: transform 0.2s ease;
    position: relative; /* Crucial for positioning child elements */
    cursor: pointer;
    border: 2px solid transparent; /* Initial transparent border for smooth transition */
    scroll-snap-align: start; /* Snap to start of item */
    flex-shrink: 0; /* Ensure cards don't shrink */
  }
  /* RGB border animation on hover */
  .movie-card:hover {
    transform: scale(1.05); /* Slight zoom on hover */
    /* RGB Border Gradient Animation */
    border: 2px solid;
    border-image: linear-gradient(to right, red, orange, yellow, green, blue, indigo, violet) 1;
    animation: rgbBorder 3s linear infinite; /* Animates the border gradient */
    box-shadow: 0 0 15px rgba(0,0,0,0.8); /* Maintain shadow on hover */
  }
  @keyframes rgbBorder {
    0% { border-image: linear-gradient(to right, red, orange, yellow, green, blue, indigo, violet) 1; }
    16.67% { border-image: linear-gradient(to right, orange, yellow, green, blue, indigo, violet, red) 1; }
    33.33% { border-image: linear-gradient(to right, yellow, green, blue, indigo, violet, red, orange) 1; }
    50% { border-image: linear-gradient(to right, green, blue, indigo, violet, red, orange, yellow) 1; }
    66.67% { border-image: linear-gradient(to right, blue, indigo, violet, red, orange, yellow, green) 1; }
    83.33% { border-image: linear-gradient(to right, indigo, violet, red, orange, yellow, green, blue) 1; }
    100% { border-image: linear-gradient(to right, violet, red, orange, yellow, green, blue, indigo) 1; }
  }

  .movie-poster {
    width: 100%;
    height: 270px; /* Standard poster height - as per your request to make it larger */
    object-fit: cover;
    display: block;
  }
  .movie-info {
    padding: 10px;
    background: rgba(0, 0, 0, 0.7); /* Translucent background for text */
    position: absolute; /* Position over the poster */
    bottom: 0;
    left: 0;
    right: 0;
    text-align: center; /* Center text */
  }
  .movie-title {
    font-size: 18px;
    font-weight: 700;
    margin: 0 0 4px 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #007bff; /* Blue for title, as in MovieDokan screenshot */
  }
  .movie-year {
    font-size: 14px;
    color: #ff8c00; /* Orange for year, as in MovieDokan screenshot */
    margin-bottom: 6px;
  }

  /* Badge Styles (for Quality & Trending) */
  .badge {
    position: absolute;
    top: 8px; /* Offset from top */
    right: 8px; /* Offset from right */
    background: #1db954; /* Default green for quality */
    color: #000;
    font-weight: 700;
    font-size: 12px;
    padding: 2px 6px;
    border-radius: 4px;
    text-transform: uppercase;
    user-select: none;
    z-index: 10; /* Ensure it's above poster */
    /* Skew/Rotate for "Trending" badge */
    transform: rotate(45deg);
    transform-origin: top right;
    right: -20px; /* Adjust to move it out partially */
    top: 15px; /* Adjust vertical position */
    width: 100px; /* Fixed width to ensure consistent angle */
    text-align: center;
    box-shadow: 0 2px 5px rgba(0,0,0,0.5);
  }
  .badge.trending {
    background: linear-gradient(45deg, #ff0077, #ff9900); /* Red-Orange gradient for trending */
    color: #fff;
    padding: 4px 15px; /* Larger padding for trending tag */
    font-size: 11px;
    letter-spacing: 1px;
  }
  .badge.trending::before {
      content: ''; /* No extra content needed for this style */
  }

  /* New styles for overlay text on poster */
  .overlay-text {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      padding: 10px;
      display: flex;
      flex-direction: column;
      align-items: flex-start; /* Align text to the left */
      z-index: 5; /* Below the trending badge */
      text-shadow: 1px 1px 3px rgba(0,0,0,0.8);
      color: #fff;
  }
  .label-badge { /* Reusing for both language and custom top_label */
      background: rgba(0, 0, 0, 0.6); /* Semi-transparent black background */
      color: #fff;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: bold;
      margin-bottom: 5px; /* Space between label and title */
      text-transform: uppercase;
  }
  .label-badge.custom-label { /* Specific style for custom top_label */
      background-color: #ff9800; /* Orange background for custom labels */
  }
  .label-badge.coming-soon-badge { /* Specific style for Coming Soon badge */
      background-color: #007bff; /* Blue background for Coming Soon */
      color: #fff;
      font-size: 11px;
      padding: 4px 8px;
  }
  .movie-top-title {
      font-size: 14px;
      font-weight: bold;
      color: #fff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      width: 100%; /* Take full width of overlay-text */
      padding-right: 5px; /* Ensure space from right edge */
  }

  .overview { display: none; } /* Overview hidden by default in card view */

  /* Mobile adjustments - START */
  @media (max-width: 768px) {
    header { padding: 8px 15px; }
    header h1 { font-size: 20px; margin: 0; }
    form { margin-left: 10px; }
    input[type="search"] { max-width: unset; font-size: 14px; padding: 6px 10px; }
    main { margin: 15px auto; padding: 0 10px; padding-bottom: 60px; }
    
    .category-header { margin-bottom: 15px; padding: 8px 0; }
    .category-header h2 { font-size: 18px; }
    .category-header .see-all-btn { padding: 6px 10px; font-size: 12px; }

    .grid { 
        grid-template-columns: none; /* Disable fixed grid columns */
        grid-auto-flow: column; /* Ensure horizontal flow */
        grid-auto-columns: minmax(130px, 1fr); /* Slightly larger columns for mobile */
        gap: 10px;
        margin-bottom: 30px;
    }
    .vertical-grid { /* Mobile adjustment for vertical grid */
        grid-auto-flow: row;
        grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); /* 2-3 columns on mobile */
        gap: 15px;
    }
    .movie-card { box-shadow: 0 0 5px rgba(0,0,0,0.5); }
    .movie-poster { height: 180px; } /* Larger height for mobile posters */
    .movie-info { padding: 8px; background: rgba(0, 0, 0, 0.7); }
    .movie-title { font-size: 14px; margin: 0 0 2px 0; } /* Larger font for mobile */
    .movie-year { font-size: 11px; margin-bottom: 4px; }
    .badge { 
        font-size: 10px; padding: 2px 5px; top: 8px; right: -15px; /* Adjust for smaller screens */
        transform: rotate(45deg); /* Keep rotation */
        width: 90px; /* Smaller width for mobile badge */
    }
    .overlay-text {
        padding: 8px; /* Smaller padding on mobile */
    }
    .label-badge {
        font-size: 11px;
        padding: 3px 6px;
        margin-bottom: 4px;
    }
    .label-badge.coming-soon-badge {
        font-size: 10px;
        padding: 3px 7px;
    }
    .movie-top-title {
        font-size: 13px;
    }
    
    .ad-container {
        padding: 5px;
        margin: 10px 0;
    }
    
    .ad-banner {
        max-height: 60px;
    }
    
    .native-ad {
        padding: 5px;
    }
    
    .native-ad img {
        width: 60px;
        height: 60px;
        margin-right: 10px;
    }
    
    .native-ad h4 {
        font-size: 14px;
    }
    
    .native-ad p {
        font-size: 12px;
    }
  }

  @media (max-width: 480px) {
      .grid { grid-auto-columns: minmax(120px,1fr); } /* Even smaller min width for very small screens */
      .vertical-grid {
          grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); /* Adjust for smaller screens */
          gap: 10px;
      }
      .movie-poster { height: 160px; } /* Adjust height for very small screens */
  }
  /* Mobile adjustments - END */

  /* Bottom Navigation Bar Styles (based on screenshot) */
  .bottom-nav {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: #1f1f1f; /* Slightly lighter dark for nav */
    display: flex; justify-content: space-around;
    padding: 10px 0;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.8);
    z-index: 200;
  }
  .nav-item {
    display: flex; flex-direction: column; align-items: center;
    color: #ccc; /* Default color for icons/text */
    font-size: 12px;
    text-align: center;
    transition: color 0.2s ease;
  }
  .nav-item:hover, .nav-item.active { /* Active state for Home */
    color: #e44d26; /* Orange color for active/hover */
  }
  .nav-item i {
    font-size: 24px;
    margin-bottom: 4px;
  }
  @media (max-width: 768px) {
      .bottom-nav { padding: 8px 0; }
      .nav-item { font-size: 10px; }
      .nav-item i { font-size: 20px; margin-bottom: 2px; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
</head>
<body>
<header>
  <h1>MovieZone</h1>
  <form method="GET" action="/">
    <input type="search" name="q" placeholder="Search movies..." value="{{ query|default('') }}" />
  </form>
</header>

{# হেডার বিজ্ঞাপন সেকশন #}
{% set header_ads = get_active_ads('header') %}
{% if header_ads %}
  <div class="ad-container">
    {% for ad in header_ads %}
      {% if ad.type == 'banner' or ad.type == 'automated' %}
        {% if ad.type == 'automated' %}
          {{ ad.ad_code | safe }}
        {% else %}
          <a href="{{ ad.target_url }}" target="_blank" class="ad-banner">
            <img src="{{ ad.image_url }}" alt="{{ ad.title }}">
          </a>
        {% endif %}
      {% elif ad.type == 'native' %}
        <div class="native-ad">
          <a href="{{ ad.target_url }}" target="_blank">
            <img src="{{ ad.image_url }}" alt="{{ ad.title }}">
            <div class="native-ad-content">
              <h4>{{ ad.title }}</h4>
              <p>{{ ad.description }}</p>
            </div>
          </a>
        </div>
      {% endif %}
    {% endfor %}
  </div>
{% endif %}

<main>
  {# Conditional rendering for full list pages vs. homepage sections #}
  {% if is_full_page_list %}
    <div class="category-header">
      <h2>{{ query }}</h2> {# query holds the title like "Trending on MovieZone" #}
      {# No "See All" button for full list pages #}
    </div>
    {% if movies|length == 0 %}
      <p style="text-align:center; color:#999; margin-top: 40px;">No content found in this category.</p>
    {% else %}
      <div class="grid vertical-grid"> {# Apply vertical-grid class here #}
        {% for m in movies %}
        <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
          {% if m.poster %}
            <img class="movie-poster" src="{{ m.poster }}" alt="{{ m.title }}">
          {% else %}
            <div style="height:270px; background:#333; display:flex;align-items:center;justify-content:center;color:#777;">
              No Image
            </div>
          {% endif %}
    
          <div class="overlay-text">
              {% if m.is_coming_soon %}
                  <span class="label-badge coming-soon-badge">COMING SOON</span>
              {% elif m.top_label %}
                  <span class="label-badge custom-label">{{ m.top_label | upper }}</span>
              {% elif m.original_language and m.original_language != 'N/A' %}
                  <span class="label-badge">{{ m.original_language | upper }}</span>
              {% endif %}
              <span class="movie-top-title" title="{{ m.title }}">{{ m.title }}</span>
          </div>
    
          {% if m.quality %}
            <div class="badge {% if m.quality == 'TRENDING' %}trending{% endif %}">{{ m.quality }}</div>
          {% endif %}
          <div class="movie-info">
            <h3 class="movie-title" title="{{ m.title }}">{{ m.title }}</h3>
            <div class="movie-year">{{ m.year }}</div>
          </div>
        </a>
        {% endfor %}
      </div>
    {% endif %}
  {% else %} {# Original home page sections #}
    {% if query %}
      <div class="category-header">
        <h2>Search Results for "{{ query }}"</h2>
      </div>
      {% if movies|length == 0 %}
        <p style="text-align:center; color:#999; margin-top: 40px;">No movies found for your search.</p>
      {% else %}
        <div class="grid vertical-grid"> {# Search results also vertical #}
          {% for m in movies %}
          <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
            {% if m.poster %}
              <img class="movie-poster" src="{{ m.poster }}" alt="{{ m.title }}">
            {% else %}
              <div style="height:270px; background:#333; display:flex;align-items:center;justify-content:center;color:#777;">
                No Image
              </div>
            {% endif %}
      
            <div class="overlay-text">
                {% if m.is_coming_soon %}
                    <span class="label-badge coming-soon-badge">COMING SOON</span>
                {% elif m.top_label %}
                    <span class="label-badge custom-label">{{ m.top_label | upper }}</span>
                {% elif m.original_language and m.original_language != 'N/A' %}
                    <span class="label-badge">{{ m.original_language | upper }}</span>
                {% endif %}
                <span class="movie-top-title" title="{{ m.title }}">{{ m.title }}</span>
            </div>
      
            {% if m.quality %}
              <div class="badge {% if m.quality == 'TRENDING' %}trending{% endif %}">{{ m.quality }}</div>
            {% endif %}
            <div class="movie-info">
              <h3 class="movie-title" title="{{ m.title }}">{{ m.title }}</h3>
              <div class="movie-year">{{ m.year }}</div>
            </div>
          </a>
          {% endfor %}
        </div>
      {% endif %}
    {% else %}
      <div class="category-header">
        <h2>Trending on MovieZone</h2>
        <a href="{{ url_for('trending_movies') }}" class="see-all-btn">See All</a>
      </div>
      {% if trending_movies|length == 0 %}
        <p style="text-align:center; color:#999;">No trending movies found.</p>
      {% else %}
        <div class="grid"> {# Homepage trending grid remains horizontal #}
          {% for m in trending_movies %}
          <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
            {% if m.poster %}
              <img class="movie-poster" src="{{ m.poster }}" alt="{{ m.title }}">
            {% else %}
              <div style="height:270px; background:#333; display:flex;align-items:center;justify-content:center;color:#777;">
                No Image
              </div>
            {% endif %}
      
            <div class="overlay-text">
                {% if m.is_coming_soon %}
                    <span class="label-badge coming-soon-badge">COMING SOON</span>
                {% elif m.top_label %}
                    <span class="label-badge custom-label">{{ m.top_label | upper }}</span>
                {% elif m.original_language and m.original_language != 'N/A' %}
                    <span class="label-badge">{{ m.original_language | upper }}</span>
                {% endif %}
                <span class="movie-top-title" title="{{ m.title }}">{{ m.title }}</span>
            </div>
      
            {% if m.quality %}
              <div class="badge {% if m.quality == 'TRENDING' %}trending{% endif %}">{{ m.quality }}</div>
            {% endif %}
            <div class="movie-info">
              <h3 class="movie-title" title="{{ m.title }}">{{ m.title }}</h3>
              <div class="movie-year">{{ m.year }}</div>
            </div>
          </a>
          {% endfor %}
        </div>
      {% endif %}

      <div class="category-header">
        <h2>Latest Movies</h2>
        <a href="{{ url_for('movies_only') }}" class="see-all-btn">See All</a>
      </div>
      {% if latest_movies|length == 0 %}
        <p style="text-align:center; color:#999;">No movies found.</p>
      {% else %}
        <div class="grid"> {# Homepage latest movies grid remains horizontal #}
          {% for m in latest_movies %}
          <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
            {% if m.poster %}
              <img class="movie-poster" src="{{ m.poster }}" alt="{{ m.title }}">
            {% else %}
              <div style="height:270px; background:#333; display:flex;align-items:center;justify-content:center;color:#777;">
                No Image
              </div>
            {% endif %}
      
            <div class="overlay-text">
                {% if m.is_coming_soon %}
                    <span class="label-badge coming-soon-badge">COMING SOON</span>
                {% elif m.top_label %}
                    <span class="label-badge custom-label">{{ m.top_label | upper }}</span>
                {% elif m.original_language and m.original_language != 'N/A' %}
                    <span class="label-badge">{{ m.original_language | upper }}</span>
                {% endif %}
                <span class="movie-top-title" title="{{ m.title }}">{{ m.title }}</span>
            </div>
      
            {% if m.quality %}
              <div class="badge {% if m.quality == 'TRENDING' %}trending{% endif %}">{{ m.quality }}</div>
            {% endif %}
            <div class="movie-info">
              <h3 class="movie-title" title="{{ m.title }}">{{ m.title }}</h3>
              <div class="movie-year">{{ m.year }}</div>
            </div>
          </a>
          {% endfor %}
        </div>
      {% endif %}

      <div class="category-header">
        <h2>Latest TV Series & Web Series</h2>
        <a href="{{ url_for('webseries') }}" class="see-all-btn">See All</a>
      </div>
      {% if latest_series|length == 0 %}
        <p style="text-align:center; color:#999;">No TV series or web series found.</p>
      {% else %}
        <div class="grid"> {# Homepage latest series grid remains horizontal #}
          {% for m in latest_series %}
          <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
            {% if m.poster %}
              <img class="movie-poster" src="{{ m.poster }}" alt="{{ m.title }}">
            {% else %}
              <div style="height:270px; background:#333; display:flex;align-items:center;justify-content:center;color:#777;">
                No Image
              </div>
            {% endif %}
      
            <div class="overlay-text">
                {% if m.is_coming_soon %}
                    <span class="label-badge coming-soon-badge">COMING SOON</span>
                {% elif m.top_label %}
                    <span class="label-badge custom-label">{{ m.top_label | upper }}</span>
                {% elif m.original_language and m.original_language != 'N/A' %}
                    <span class="label-badge">{{ m.original_language | upper }}</span>
                {% endif %}
                <span class="movie-top-title" title="{{ m.title }}">{{ m.title }}</span>
            </div>
      
            {% if m.quality %}
              <div class="badge {% if m.quality == 'TRENDING' %}trending{% endif %}">{{ m.quality }}</div>
            {% endif %}
            <div class="movie-info">
              <h3 class="movie-title" title="{{ m.title }}">{{ m.title }}</h3>
              <div class="movie-year">{{ m.year }}</div>
            </div>
          </a>
          {% endfor %}
        </div>
      {% endif %}

      <div class="category-header">
        <h2>Coming Soon</h2>
        <a href="{{ url_for('coming_soon') }}" class="see-all-btn">See All</a>
      </div>
      {% if coming_soon_movies|length == 0 %}
        <p style="text-align:center; color:#999;">No upcoming movies found.</p>
      {% else %}
        <div class="grid"> {# Homepage coming soon grid remains horizontal #}
          {% for m in coming_soon_movies %}
          <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
            {% if m.poster %}
              <img class="movie-poster" src="{{ m.poster }}" alt="{{ m.title }}">
            {% else %}
              <div style="height:270px; background:#333; display:flex;align-items:center;justify-content:center;color:#777;">
                No Image
              </div>
            {% endif %}
      
            <div class="overlay-text">
                <span class="label-badge coming-soon-badge">COMING SOON</span>
                <span class="movie-top-title" title="{{ m.title }}">{{ m.title }}</span>
            </div>
      
            {% if m.quality %}
              <div class="badge {% if m.quality == 'TRENDING' %}trending{% endif %}">{{ m.quality }}</div>
            {% endif %}
            <div class="movie-info">
              <h3 class="movie-title" title="{{ m.title }}">{{ m.title }}</h3>
              <div class="movie-year">{{ m.year }}</div>
            </div>
          </a>
          {% endfor %}
        </div>
      {% endif %}
    {% endif %}
  {% endif %} {# End of is_full_page_list / else query block #}
</main>
<nav class="bottom-nav">
  <a href="{{ url_for('home') }}" class="nav-item {% if request.endpoint == 'home' and not request.args.get('q') %}active{% endif %}">
    <i class="fas fa-home"></i>
    <span>Home</span>
  </a>
  <a href="{{ url_for('movies_only') }}" class="nav-item {% if request.endpoint == 'movies_only' %}active{% endif %}">
    <i class="fas fa-film"></i>
    <span>Movie</span>
  </a>
  <a href="https://t.me/Movie_Request_Group_23" class="nav-item" target="_blank" rel="noopener">
    <i class="fas fa-plus-circle"></i>
    <span>Request</span>
  </a>
  <a href="{{ url_for('webseries') }}" class="nav-item {% if request.endpoint == 'webseries' %}active{% endif %}">
    <i class="fas fa-tv"></i>
    <span>Web Series</span>
  </a>
  <a href="{{ url_for('home') }}" class="nav-item {% if request.args.get('q') %}active{% endif %}">
    <i class="fas fa-search"></i>
    <span>Search</span>
  </a>
</nav>
</body>
</html>
"""
# --- END OF index_html TEMPLATE ---

# --- START OF detail_html TEMPLATE ---
detail_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{{ movie.title if movie else "Movie Not Found" }} - MovieZone Details</title>
<style>
  /* General styles (similar to index_html for consistency) */
  * { box-sizing: border-box; margin: 0; padding: 0;}
  body { margin: 0; background: #121212; color: #eee; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
  a { text-decoration: none; color: inherit; }
  a:hover { color: #1db954; }

  header {
    position: sticky; top: 0; left: 0; right: 0;
    background: #181818; padding: 10px 20px;
    display: flex; justify-content: flex-start; align-items: center; z-index: 100;
    box-shadow: 0 2px 5px rgba(0,0,0,0.7);
  }
  header h1 {
    margin: 0; font-weight: 700; font-size: 24px;
    background: linear-gradient(270deg, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3);
    background-size: 400% 400%; -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    animation: gradientShift 10s ease infinite;
    flex-grow: 1;
    text-align: center;
  }
  @keyframes gradientShift {
    0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; }
  }
  .back-button {
      color: #1db954;
      font-size: 18px;
      position: absolute;
      left: 20px;
      z-index: 101;
  }
  .back-button i { margin-right: 5px; }
  
  /* Ad Container Styles */
  .ad-container {
    width: 100%;
    text-align: center;
    margin: 15px 0;
    padding: 10px;
    background: #1f1f1f;
    border-radius: 8px;
    overflow: hidden;
  }
  
  .ad-banner {
    display: block;
    margin: 0 auto;
    max-width: 100%;
    max-height: 90px;
    border-radius: 5px;
  }
  
  .native-ad {
    display: flex;
    align-items: center;
    background: #282828;
    border-radius: 8px;
    padding: 10px;
    text-align: left;
  }
  
  .native-ad img {
    width: 80px;
    height: 80px;
    object-fit: cover;
    border-radius: 5px;
    margin-right: 15px;
  }
  
  .native-ad-content {
    flex-grow: 1;
  }
  
  .native-ad h4 {
    font-size: 16px;
    margin-bottom: 5px;
    color: #1db954;
  }
  
  .native-ad p {
    font-size: 14px;
    color: #ccc;
  }

  /* Detail Page Specific Styles */
  .movie-detail-container {
    max-width: 1000px;
    margin: 20px auto;
    padding: 25px;
    background: #181818;
    border-radius: 8px;
    box-shadow: 0 0 15px rgba(0,0,0,0.7);
    display: flex;
    flex-direction: column;
    gap: 25px;
  }

  .main-info {
      display: flex;
      flex-direction: column;
      gap: 25px;
  }

  .detail-poster-wrapper {
      position: relative;
      width: 100%;
      max-width: 300px;
      flex-shrink: 0;
      align-self: center;
  }
  .detail-poster {
    width: 100%;
    height: auto;
    border-radius: 8px;
    box-shadow: 0 0 10px rgba(0,0,0,0.5);
    display: block;
  }
  .detail-poster-wrapper .badge {
      position: absolute;
      top: 10px;
      left: 10px;
      font-size: 14px;
      padding: 4px 8px;
      border-radius: 5px;
      background: #1db954; /* Consistent badge color */
      color: #000;
      font-weight: 700;
      text-transform: uppercase;
  }
  .detail-poster-wrapper .badge.trending {
    background: linear-gradient(45deg, #ff0077, #ff9900);
    color: #fff;
  }
  .detail-poster-wrapper .coming-soon-badge {
      position: absolute;
      top: 10px;
      left: 10px;
      font-size: 14px;
      padding: 4px 8px;
      border-radius: 5px;
      background-color: #007bff; /* Blue for Coming Soon */
      color: #fff;
      font-weight: 700;
      text-transform: uppercase;
  }

  .detail-info {
    flex-grow: 1;
  }
  .detail-title {
    font-size: 38px;
    font-weight: 700;
    margin: 0 0 10px 0;
    color: #eee;
    text-shadow: 0 0 5px rgba(0,0,0,0.5);
  }
  .detail-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 15px;
      margin-bottom: 20px;
      font-size: 16px;
      color: #ccc;
  }
  .detail-meta span {
      background: #282828;
      padding: 5px 10px;
      border-radius: 5px;
      white-space: nowrap;
  }
  .detail-meta strong {
      color: #fff;
  }

  .detail-overview {
    font-size: 17px;
    line-height: 1.7;
    color: #ccc;
    margin-bottom: 30px;
  }

  /* --- DOWNLOAD LINKS SECTION --- */
  .download-section {
    width: 100%;
    text-align: center;
    margin-top: 30px;
    background: #1f1f1f;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 0 10px rgba(0,0,0,0.5);
  }
  .download-section h3 {
    font-size: 24px;
    font-weight: 700;
    color: #00ff00; /* Green color for heading */
    margin-bottom: 20px;
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 10px;
  }
  .download-section h3::before,
  .download-section h3::after {
    content: '[↓]';
    color: #00ff00;
    font-size: 20px;
  }

  .download-item {
    margin-bottom: 15px;
  }
  .download-quality-info {
    font-size: 18px;
    color: #ff9900; /* Orange color for quality info */
    margin-bottom: 10px;
    font-weight: 600;
  }
  .download-button-wrapper {
    width: 100%;
    max-width: 300px; /* Limit button width */
    margin: 0 auto;
  }
  .download-button {
    display: block; /* Make button full width of its wrapper */
    padding: 12px 20px;
    border-radius: 30px; /* Pill shape */
    background: linear-gradient(to right, #6a0dad, #8a2be2, #4b0082); /* Purple gradient */
    color: #fff;
    font-size: 18px;
    font-weight: 700;
    text-align: center;
    transition: all 0.3s ease;
    box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    border: none;
  }
  .download-button:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 15px rgba(0,0,0,0.7);
    background: linear-gradient(to right, #7b2df2, #9a4beb, #5c1bb2); /* Slightly brighter purple */
  }

  .no-link-message {
      color: #999;
      font-size: 16px;
      text-align: center;
      width: 100%;
      padding: 20px;
      background: #1f1f1f;
      border-radius: 8px;
  }


  /* Responsive Adjustments for Detail Page */
  @media (min-width: 769px) {
      .main-info {
          flex-direction: row;
          align-items: flex-start;
      }
      .detail-poster-wrapper {
          margin-right: 40px;
      }
      .detail-title {
          font-size: 44px;
      }
      /* No direct "action-buttons" anymore, removed specific style */
  }

  @media (max-width: 768px) {
    header h1 { font-size: 20px; margin: 0; }
    .back-button { font-size: 16px; left: 15px; }
    .movie-detail-container { padding: 15px; margin: 15px auto; gap: 15px; }
    .main-info { gap: 15px; }
    .detail-poster-wrapper { max-width: 180px; }
    .detail-poster-wrapper .badge, .detail-poster-wrapper .coming-soon-badge { font-size: 12px; padding: 2px 6px; top: 8px; left: 8px; }
    .detail-title { font-size: 28px; }
    .detail-meta { font-size: 14px; gap: 10px; margin-bottom: 15px; }
    .detail-overview { font-size: 15px; margin-bottom: 20px; }
    
    .download-section h3 { font-size: 20px; }
    .download-section h3::before,
    .download-section h3::after { font-size: 18px; }
    .download-quality-info { font-size: 16px; }
    .download-button { font-size: 16px; padding: 10px 15px; }
    
    .ad-container {
        padding: 5px;
        margin: 10px 0;
    }
    
    .ad-banner {
        max-height: 60px;
    }
    
    .native-ad {
        padding: 5px;
    }
    
    .native-ad img {
        width: 60px;
        height: 60px;
        margin-right: 10px;
    }
    
    .native-ad h4 {
        font-size: 14px;
    }
    
    .native-ad p {
        font-size: 12px;
    }
  }

  @media (max-width: 480px) {
      .detail-title { font-size: 22px; }
      .detail-meta { font-size: 13px; }
      .detail-overview { font-size: 14px; }
      .download-section h3 { font-size: 18px; }
      .download-section h3::before,
      .download-section h3::after { font-size: 16px; }
      .download-quality-info { font-size: 14px; }
      .download-button { font-size: 14px; padding: 8px 12px; }
  }

  /* Bottom nav for consistency (same as index_html) */
  .bottom-nav {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: #1f1f1f; display: flex; justify-content: space-around;
    padding: 10px 0; box-shadow: 0 -2px 5px rgba(0,0,0,0.7); z-index: 200;
  }
  .nav-item {
    display: flex; flex-direction: column; align-items: center;
    color: #ccc; font-size: 12px; text-align: center; transition: color 0.2s ease;
  }
  .nav-item:hover { color: #e44d26; } /* Orange color for active/hover */
  .nav-item i { font-size: 24px; margin-bottom: 4px; }
  @media (max-width: 768px) {
      .bottom-nav { padding: 8px 0; }
      .nav-item { font-size: 10px; }
      .nav-item i { font-size: 20px; margin-bottom: 2px; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
</head>
<body>
<header>
  <a href="{{ url_for('home') }}" class="back-button"><i class="fas fa-arrow-left"></i>Back</a>
  <h1>MovieZone</h1>
</header>

{# হেডার বিজ্ঞাপন সেকশন #}
{% set header_ads = get_active_ads('header') %}
{% if header_ads %}
  <div class="ad-container">
    {% for ad in header_ads %}
      {% if ad.type == 'banner' or ad.type == 'automated' %}
        {% if ad.type == 'automated' %}
          {{ ad.ad_code | safe }}
        {% else %}
          <a href="{{ ad.target_url }}" target="_blank" class="ad-banner">
            <img src="{{ ad.image_url }}" alt="{{ ad.title }}">
          </a>
        {% endif %}
      {% elif ad.type == 'native' %}
        <div class="native-ad">
          <a href="{{ ad.target_url }}" target="_blank">
            <img src="{{ ad.image_url }}" alt="{{ ad.title }}">
            <div class="native-ad-content">
              <h4>{{ ad.title }}</h4>
              <p>{{ ad.description }}</p>
            </div>
          </a>
        </div>
      {% endif %}
    {% endfor %}
  </div>
{% endif %}

<main>
  {% if movie %}
  <div class="movie-detail-container">
    <div class="main-info">
        <div class="detail-poster-wrapper">
            {% if movie.poster %}
              <img class="detail-poster" src="{{ movie.poster }}" alt="{{ movie.title }}">
            {% else %}
              <div class="detail-poster" style="background:#333; display:flex;align-items:center;justify-content:center;color:#777; font-size:18px; min-height: 250px;">
                No Image
              </div>
            {% endif %}
            {% if movie.is_coming_soon %}
                <div class="coming-soon-badge">COMING SOON</div>
            {% elif movie.quality %}
              <div class="badge {% if movie.quality == 'TRENDING' %}trending{% endif %}">{{ movie.quality }}</div>
            {% endif %}
        </div>
        <div class="detail-info">
          <h2 class="detail-title">{{ movie.title }}</h2>
          <div class="detail-meta">
              {% if movie.release_date %}<span><strong>Release:</strong> {{ movie.release_date }}</span>{% endif %}
              {% if movie.vote_average %}<span><strong>Rating:</strong> {{ "%.1f"|format(movie.vote_average) }}/10 <i class="fas fa-star" style="color:#FFD700;"></i></span>{% endif %}
              {% if movie.original_language %}<span><strong>Language:</strong> {{ movie.original_language | upper }}</span>{% endif %}
              {% if movie.genres %}<span><strong>Genres:</strong> {{ movie.genres | join(', ') }}</span>{% endif %}
          </div>
          <p class="detail-overview">{{ movie.overview }}</p>
        </div>
    </div>
    
    <div class="download-section">
      {% if movie.type == 'movie' %}
        <h3>Download Links</h3>
        {% if movie.links and movie.links|length > 0 %}
          {% for link_item in movie.links %}
          <div class="download-item">
            <p class="download-quality-info">({{ link_item.quality }}) [{{ link_item.size }}]</p>
            <div class="download-button-wrapper">
              <a class="download-button" href="{{ link_item.url }}" target="_blank" rel="noopener">Download</a>
            </div>
          </div>
          {% endfor %}
        {% else %}
          <p class="no-link-message">No download links available yet.</p>
        {% endif %}
      {% elif movie.type == 'series' and movie.episodes and movie.episodes|length > 0 %}
        <h3>Episodes</h3>
        {% for episode in movie.episodes | sort(attribute='episode_number') %}
        <div class="download-item" style="border-top: 1px solid #333; padding-top: 15px; margin-top: 15px;">
          <h4 style="color: #1db954; font-size: 20px; margin-bottom: 10px;">Episode {{ episode.episode_number }}: {{ episode.title }}</h4>
          {% if episode.overview %}
            <p style="color: #ccc; font-size: 15px; margin-bottom: 10px;">{{ episode.overview }}</p>
          {% endif %}
          {% if episode.links and episode.links|length > 0 %}
            {% for link_item in episode.links %}
            <div class="download-button-wrapper" style="margin-bottom: 10px;">
              <a class="download-button" href="{{ link_item.url }}" target="_blank" rel="noopener">Download ({{ link_item.quality }}) [{{ link_item.size }}]</a>
            </div>
            {% endfor %}
          {% else %}
            <p class="no-link-message" style="margin-top: 0; padding: 0; background: none;">No download links for this episode.</p>
          {% endif %}
        </div>
        {% endfor %}
      {% else %}
        <p class="no-link-message">No download links or episodes available yet for this content type.</p>
      {% endif %}
    </div>

  </div>
  {% else %}
    <p style="text-align:center; color:#999; margin-top: 40px;">Movie not found.</p>
  {% endif %}
</main>
<nav class="bottom-nav">
  <a href="{{ url_for('home') }}" class="nav-item {% if request.endpoint == 'home' and not request.args.get('q') %}active{% endif %}">
    <i class="fas fa-home"></i>
    <span>Home</span>
  </a>
  <a href="{{ url_for('movies_only') }}" class="nav-item {% if request.endpoint == 'movies_only' %}active{% endif %}">
    <i class="fas fa-film"></i>
    <span>Movie</span>
  </a>
  <a href="https://t.me/Movie_Request_Group_23" class="nav-item" target="_blank" rel="noopener">
    <i class="fas fa-plus-circle"></i>
    <span>Request</span>
  </a>
  <a href="{{ url_for('webseries') }}" class="nav-item {% if request.endpoint == 'webseries' %}active{% endif %}">
    <i class="fas fa-tv"></i>
    <span>Web Series</span>
  </a>
  <a href="{{ url_for('home') }}" class="nav-item {% if request.args.get('q') %}active{% endif %}">
    <i class="fas fa-search"></i>
    <span>Search</span>
  </a>
</nav>
</body>
</html>
"""
# --- END OF detail_html TEMPLATE ---

# --- START OF admin_html TEMPLATE ---
admin_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Admin Panel - MovieZone</title>
  <style>
    body { font-family: Arial, sans-serif; background: #121212; color: #eee; padding: 20px; }
    h2 { 
      background: linear-gradient(270deg, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3);
      background-size: 400% 400%;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      animation: gradientShift 10s ease infinite;
      display: inline-block;
      font-size: 28px;
      margin-bottom: 20px;
    }
    @keyframes gradientShift {
      0% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
      100% { background-position: 0% 50%; }
    }
    form { max-width: 600px; margin-bottom: 40px; border: 1px solid #333; padding: 20px; border-radius: 8px;}
    
    .form-group {
        margin-bottom: 15px;
    }
    .form-group label {
        display: block;
        margin-bottom: 5px;
        font-weight: bold;
        color: #ddd;
    }
    input[type="text"], input[type="url"], textarea, button, select, input[type="number"], input[type="search"] { /* Added input[type="search"] */
      width: 100%;
      padding: 10px;
      margin-bottom: 15px;
      border-radius: 5px;
      border: none;
      font-size: 16px;
      background: #222;
      color: #eee;
    }
    input[type="checkbox"] {
        width: auto;
        margin-right: 10px;
    }
    textarea {
        resize: vertical;
        min-height: 80px;
    }
    .link-input-group input[type="url"] {
        margin-bottom: 5px;
    }
    .link-input-group p {
        font-size: 14px;
        color: #bbb;
        margin-bottom: 5px;
    }

    button {
      background: #1db954;
      color: #000;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.3s ease;
    }
    button:hover {
      background: #17a34a;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 20px;
    }
    th, td {
        padding: 10px;
        text-align: left;
        border-bottom: 1px solid #333;
    }
    th {
        background: #282828;
        color: #eee;
    }
    td {
        background: #181818;
    }
    .action-buttons {
        display: flex;
        gap: 5px;
    }
    .delete-btn {
        background: #e44d26;
        color: #fff;
        padding: 5px 10px;
        border-radius: 5px;
        border: none;
        cursor: pointer;
        transition: background 0.3s ease;
        font-size: 14px;
        width: auto;
        margin-bottom: 0;
    }
    .delete-btn:hover {
        background: #d43d16;
    }
    .edit-btn {
        background: #007bff; /* Blue color for edit */
        color: #fff;
        padding: 5px 10px;
        border-radius: 5px;
        text-decoration: none;
        font-size: 14px;
        width: auto;
        margin-bottom: 0;
        display: inline-block; /* Allows padding and margin */
        transition: background 0.3s ease;
    }
    .edit-btn:hover {
        background: #0056b3;
    }
    .movie-list-container {
        max-width: 800px;
        margin-top: 40px;
        background: #181818;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 0 10px rgba(0,0,0,0.5);
    }
    .admin-links {
        display: flex;
        justify-content: center;
        gap: 20px;
        margin-top: 30px;
    }
    .admin-link {
        background: #8a2be2;
        color: #fff;
        padding: 12px 25px;
        border-radius: 30px;
        text-decoration: none;
        font-weight: bold;
        display: inline-block;
        transition: transform 0.2s ease;
    }
    .admin-link:hover {
        transform: translateY(-3px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    }
    .admin-link.blue {
        background: #007bff;
    }
    .admin-link.green {
        background: #28a745;
    }
  </style>
</head>
<body>
  <h2>Add New Movie</h2>
  <form method="post">
    <!-- ... (existing movie form remains unchanged) ... -->
  </form>

  <h2>Search Content</h2>
  <form method="GET" action="{{ url_for('admin') }}">
    <div class="form-group">
      <label for="admin_search_query">Search by Title:</label>
      <input type="search" name="q" id="admin_search_query" placeholder="Search content by title..." value="{{ admin_query|default('') }}" />
    </div>
    <button type="submit">Search</button>
  </form>

  <hr>

  <h2>Manage Existing Content {% if admin_query %}for "{{ admin_query }}"{% endif %}</h2>
  <div class="movie-list-container">
    <!-- ... (existing movie list remains unchanged) ... -->
  </div>
  
  <div class="admin-links">
    <a href="{{ url_for('ad_admin') }}" class="admin-link">Manage Advertisements</a>
    <a href="{{ url_for('ad_providers') }}" class="admin-link blue">Manage Ad Providers</a>
    <a href="{{ url_for('logout') }}" class="admin-link green">Logout</a>
  </div>
</body>
</html>
"""
# --- END OF admin_html TEMPLATE ---

# --- START OF ad_admin_html TEMPLATE ---
ad_admin_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Ad Management - MovieZone</title>
  <style>
    /* ... (existing CSS remains unchanged) ... */
  </style>
</head>
<body>
  <a href="{{ url_for('admin') }}" class="back-to-admin">&larr; Back to Main Admin</a>
  <h2>Manage Advertisements</h2>
  
  <h3>Add New Advertisement</h3>
  <form method="post" action="/ad_admin">
    <!-- ... (existing ad form remains unchanged) ... -->
  </form>
  
  <h3>Existing Advertisements</h3>
  <!-- ... (existing ad list remains unchanged) ... -->
</body>
</html>
"""
# --- END OF ad_admin_html TEMPLATE ---

# --- START OF ad_providers_html TEMPLATE ---
ad_providers_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Ad Providers - MovieZone</title>
  <style>
    body { font-family: Arial, sans-serif; background: #121212; color: #eee; padding: 20px; }
    h2 { 
      background: linear-gradient(270deg, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3);
      background-size: 400% 400%;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      animation: gradientShift 10s ease infinite;
      display: inline-block;
      font-size: 28px;
      margin-bottom: 20px;
    }
    @keyframes gradientShift {
      0% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
      100% { background-position: 0% 50%; }
    }
    form { max-width: 600px; margin-bottom: 40px; border: 1px solid #333; padding: 20px; border-radius: 8px;}
    
    .form-group {
        margin-bottom: 15px;
    }
    .form-group label {
        display: block;
        margin-bottom: 5px;
        font-weight: bold;
        color: #ddd;
    }
    input[type="text"], input[type="url"], textarea, button, select, input[type="number"] {
      width: 100%;
      padding: 10px;
      margin-bottom: 15px;
      border-radius: 5px;
      border: none;
      font-size: 16px;
      background: #222;
      color: #eee;
    }
    input[type="checkbox"] {
        width: auto;
        margin-right: 10px;
    }
    textarea {
        resize: vertical;
        min-height: 80px;
    }

    button {
      background: #1db954;
      color: #000;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.3s ease;
    }
    button:hover {
      background: #17a34a;
    }
    .back-to-admin {
        display: inline-block;
        margin-bottom: 20px;
        color: #1db954;
        text-decoration: none;
        font-weight: bold;
    }
    .back-to-admin:hover {
        text-decoration: underline;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 20px;
    }
    th, td {
        padding: 10px;
        text-align: left;
        border-bottom: 1px solid #333;
    }
    th {
        background: #282828;
        color: #eee;
    }
    td {
        background: #181818;
    }
    .action-buttons {
        display: flex;
        gap: 5px;
    }
    .delete-btn {
        background: #e44d26;
        color: #fff;
        padding: 5px 10px;
        border-radius: 5px;
        border: none;
        cursor: pointer;
        transition: background 0.3s ease;
        font-size: 14px;
        width: auto;
        margin-bottom: 0;
    }
    .delete-btn:hover {
        background: #d43d16;
    }
    .edit-btn {
        background: #007bff;
        color: #fff;
        padding: 5px 10px;
        border-radius: 5px;
        text-decoration: none;
        font-size: 14px;
        width: auto;
        margin-bottom: 0;
        display: inline-block;
        transition: background 0.3s ease;
    }
    .edit-btn:hover {
        background: #0056b3;
    }
    .ad-preview {
        max-width: 300px;
        margin: 10px 0;
        border: 1px solid #444;
        padding: 10px;
        border-radius: 5px;
    }
    .ad-preview img {
        max-width: 100%;
        display: block;
        margin-bottom: 10px;
    }
    .active-status {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 5px;
    }
    .active-status.active {
        background-color: #1db954;
    }
    .active-status.inactive {
        background-color: #e44d26;
    }
  </style>
</head>
<body>
  <a href="{{ url_for('admin') }}" class="back-to-admin">&larr; Back to Main Admin</a>
  <h2>Manage Ad Providers</h2>
  
  <h3>Add New Provider</h3>
  <form method="post" action="/save_provider">
    <input type="hidden" name="provider_id" value="{{ provider._id if provider else '' }}">
    
    <div class="form-group">
      <label for="provider_name">Provider Name:</label>
      <input type="text" name="provider_name" id="provider_name" 
             value="{{ provider.name if provider else '' }}" placeholder="e.g., Google AdSense" required>
    </div>
    
    <div class="form-group">
      <label for="api_endpoint">API Endpoint:</label>
      <input type="url" name="api_endpoint" id="api_endpoint" 
             value="{{ provider.api_endpoint if provider else '' }}" placeholder="API endpoint URL" required>
    </div>
    
    <div class="form-group">
      <label for="api_key">API Key:</label>
      <input type="text" name="api_key" id="api_key" 
             value="{{ provider.api_key if provider else '' }}" placeholder="API key" required>
    </div>
    
    <div class="form-group">
      <label>Supported Ad Formats:</label>
      <div>
        <input type="checkbox" name="ad_formats" value="banner" id="format_banner"
               {% if provider and 'banner' in provider.ad_formats %}checked{% endif %}>
        <label for="format_banner">Banner</label>
      </div>
      <div>
        <input type="checkbox" name="ad_formats" value="native" id="format_native"
               {% if provider and 'native' in provider.ad_formats %}checked{% endif %}>
        <label for="format_native">Native</label>
      </div>
      <div>
        <input type="checkbox" name="ad_formats" value="interstitial" id="format_interstitial"
               {% if provider and 'interstitial' in provider.ad_formats %}checked{% endif %}>
        <label for="format_interstitial">Interstitial</label>
      </div>
    </div>
    
    <div class="form-group">
      <label for="priority">Priority (lower number = higher priority):</label>
      <input type="number" name="priority" id="priority" 
             value="{{ provider.priority if provider else 0 }}" min="0" required>
    </div>
    
    <div class="form-group">
      <input type="checkbox" name="is_active" id="is_active" value="true"
             {% if not provider or provider.is_active %}checked{% endif %}>
      <label for="is_active" style="display: inline-block;">Active</label>
    </div>
    
    <button type="submit">Save Provider</button>
  </form>

  <h3>Current Providers</h3>
  {% if providers %}
  <table>
    <thead>
      <tr>
        <th>Name</th>
        <th>Endpoint</th>
        <th>Formats</th>
        <th>Priority</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for p in providers %}
      <tr>
        <td>{{ p.name }}</td>
        <td>{{ p.api_endpoint[:30] }}{% if p.api_endpoint|length > 30 %}...{% endif %}</td>
        <td>{{ p.ad_formats | join(', ') }}</td>
        <td>{{ p.priority }}</td>
        <td>
          <span class="active-status {% if p.is_active %}active{% else %}inactive{% endif %}"></span>
          {% if p.is_active %}Active{% else %}Inactive{% endif %}
        </td>
        <td class="action-buttons">
          <a href="{{ url_for('edit_provider', provider_id=p._id) }}" class="edit-btn">Edit</a>
          <button class="delete-btn" onclick="confirmDelete('{{ p._id }}', '{{ p.name }}')">Delete</button>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p style="text-align:center; color:#999;">No ad providers found.</p>
  {% endif %}
  
  <script>
    function confirmDelete(providerId, providerName) {
      if (confirm('Are you sure you want to delete "' + providerName + '"?')) {
        window.location.href = '/delete_provider/' + providerId;
      }
    }
  </script>
</body>
</html>
"""
# --- END OF ad_providers_html TEMPLATE ---

# --- START OF edit_movie.html TEMPLATE ---
edit_movie_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Edit Content - MovieZone</title>
  <style>
    body { font-family: Arial, sans-serif; background: #121212; color: #eee; padding: 20px; }
    h2 { 
      background: linear-gradient(270deg, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3);
      background-size: 400% 400%;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      animation: gradientShift 10s ease infinite;
      display: inline-block;
      font-size: 28px;
      margin-bottom: 20px;
    }
    @keyframes gradientShift {
      0% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
      100% { background-position: 0% 50%; }
    }
    form { max-width: 600px; margin-bottom: 40px; border: 1px solid #333; padding: 20px; border-radius: 8px;}
    
    .form-group {
        margin-bottom: 15px;
    }
    .form-group label {
        display: block;
        margin-bottom: 5px;
        font-weight: bold;
        color: #ddd;
    }
    input[type="text"], input[type="url"], textarea, button, select, input[type="number"] {
      width: 100%;
      padding: 10px;
      margin-bottom: 15px;
      border-radius: 5px;
      border: none;
      font-size: 16px;
      background: #222;
      color: #eee;
    }
    input[type="checkbox"] {
        width: auto;
        margin-right: 10px;
    }
    textarea {
        resize: vertical;
        min-height: 80px;
    }
    .link-input-group input[type="url"] {
        margin-bottom: 5px;
    }
    .link-input-group p {
        font-size: 14px;
        color: #bbb;
        margin-bottom: 5px;
    }

    button {
      background: #1db954;
      color: #000;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.3s ease;
    }
    button:hover {
      background: #17a34a;
    }
    .back-to-admin {
        display: inline-block;
        margin-bottom: 20px;
        color: #1db954;
        text-decoration: none;
        font-weight: bold;
    }
    .back-to-admin:hover {
        text-decoration: underline;
    }
  </style>
</head>
<body>
  <a href="{{ url_for('admin') }}" class="back-to-admin">&larr; Back to Admin Panel</a>
  <h2>Edit Content: {{ movie.title }}</h2>
  <form method="post">
    <!-- ... (existing movie edit form remains unchanged) ... -->
  </form>
</body>
</html>
"""
# --- END OF edit_movie.html TEMPLATE ---

# --- START OF edit_ad.html TEMPLATE ---
edit_ad_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Edit Advertisement - MovieZone</title>
  <style>
    /* ... (existing CSS remains unchanged) ... */
  </style>
</head>
<body>
  <a href="{{ url_for('ad_admin') }}" class="back-to-admin">&larr; Back to Ad Management</a>
  <h2>Edit Advertisement: {{ ad.title }}</h2>
  <form method="post">
    <!-- ... (existing ad edit form remains unchanged) ... -->
  </form>
</body>
</html>
"""
# --- END OF edit_ad.html TEMPLATE ---

# --- Application Routes ---
@app.route('/')
def home():
    query = request.args.get('q')
    
    movies_list = []
    trending_movies_list = []
    latest_movies_list = []
    latest_series_list = []
    coming_soon_movies_list = []

    is_full_page_list = False

    if query:
        result = movies.find({"title": {"$regex": query, "$options": "i"}})
        movies_list = list(result)
        is_full_page_list = True
        
        # Convert ObjectId to string for search results
        for m in movies_list:
            m['_id'] = str(m['_id'])
    else:
        # Fetch data for homepage sections
        trending_movies_result = movies.find({"quality": "TRENDING"}).sort('_id', -1).limit(6)
        latest_movies_result = movies.find({
            "type": "movie",
            "quality": {"$ne": "TRENDING"},
            "is_coming_soon": {"$ne": True}
        }).sort('_id', -1).limit(6)
        latest_series_result = movies.find({
            "type": "series",
            "quality": {"$ne": "TRENDING"},
            "is_coming_soon": {"$ne": True}
        }).sort('_id', -1).limit(6)
        coming_soon_result = movies.find({"is_coming_soon": True}).sort('_id', -1).limit(6)

        trending_movies_list = list(trending_movies_result)
        latest_movies_list = list(latest_movies_result)
        latest_series_list = list(latest_series_result)
        coming_soon_movies_list = list(coming_soon_result)

        # Convert ObjectId to string for all lists
        for lst in [trending_movies_list, latest_movies_list, latest_series_list, coming_soon_movies_list]:
            for m in lst:
                m['_id'] = str(m['_id'])

    return render_template_string(
        index_html, 
        movies=movies_list,
        query=query,
        trending_movies=trending_movies_list,
        latest_movies=latest_movies_list,
        latest_series=latest_series_list,
        coming_soon_movies=coming_soon_movies_list,
        is_full_page_list=is_full_page_list,
        get_active_ads=get_active_ads
    )

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if movie:
            movie['_id'] = str(movie['_id'])
            
            # Fetch additional details from TMDb if API key is available
            should_fetch_tmdb = TMDB_API_KEY and (not movie.get("tmdb_id") or movie.get("overview") == "No overview available." or not movie.get("poster")) and movie.get("type") == "movie"

            if should_fetch_tmdb:
                tmdb_id = movie.get("tmdb_id") 
                
                # If TMDb ID is not stored, search by title first
                if not tmdb_id:
                    tmdb_search_type = "movie" if movie.get("type") == "movie" else "tv"
                    search_url = f"https://api.themoviedb.org/3/search/{tmdb_search_type}?api_key={TMDB_API_KEY}&query={movie['title']}"
                    try:
                        search_res = requests.get(search_url, timeout=5).json()
                        if search_res and "results" in search_res and search_res["results"]:
                            tmdb_id = search_res["results"][0].get("id")
                            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": {"tmdb_id": tmdb_id}})
                        else:
                            print(f"No search results found on TMDb for title: {movie['title']} ({tmdb_search_type})")
                            tmdb_id = None
                    except requests.exceptions.RequestException as e:
                        print(f"Error connecting to TMDb API for search '{movie['title']}': {e}")
                        tmdb_id = None
                    except Exception as e:
                        print(f"An unexpected error occurred during TMDb search: {e}")
                        tmdb_id = None

                # If TMDb ID is found (either from DB or search), fetch full details
                if tmdb_id:
                    tmdb_detail_type = "movie" if movie.get("type") == "movie" else "tv"
                    tmdb_detail_url = f"https://api.themoviedb.org/3/{tmdb_detail_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
                    try:
                        res = requests.get(tmdb_detail_url, timeout=5).json()
                        if res:
                            if movie.get("overview") == "No overview available." and res.get("overview"):
                                movie["overview"] = res.get("overview")
                            if not movie.get("poster") and res.get("poster_path"):
                                movie["poster"] = f"https://image.tmdb.org/t/p/w500{res['poster_path']}"
                            
                            release_date = res.get("release_date") or res.get("first_air_date")
                            if movie.get("year") == "N/A" and release_date:
                                movie["year"] = release_date[:4]
                                movie["release_date"] = release_date
                            
                            if movie.get("vote_average") is None and res.get("vote_average"):
                                movie["vote_average"] = res.get("vote_average")
                            if movie.get("original_language") == "N/A" and res.get("original_language"):
                                movie["original_language"] = res.get("original_language")
                            
                            genres_names = []
                            for genre_obj in res.get("genres", []):
                                if isinstance(genre_obj, dict) and genre_obj.get("id") in TMDb_Genre_Map:
                                    genres_names.append(TMDb_Genre_Map[genre_obj["id"]])
                            if (not movie.get("genres") or movie["genres"] == []) and genres_names:
                                movie["genres"] = genres_names

                            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": {
                                "overview": movie["overview"],
                                "poster": movie["poster"],
                                "year": movie["year"],
                                "release_date": movie["release_date"],
                                "vote_average": movie["vote_average"],
                                "original_language": movie["original_language"],
                                "genres": movie["genres"]
                            }})
                    except requests.exceptions.RequestException as e:
                        print(f"Error connecting to TMDb API for detail '{movie_id}': {e}")
                    except Exception as e:
                        print(f"An unexpected error occurred while fetching TMDb detail data: {e}")
                else:
                    print(f"TMDb ID not found for movie '{movie.get('title', movie_id)}'. Skipping TMDb detail fetch.")
            else:
                print("Skipping TMDb API call for movie details (not a movie, no key, or data already present).")

        return render_template_string(detail_html, movie=movie, get_active_ads=get_active_ads)
    except Exception as e:
        print(f"Error fetching movie detail for ID {movie_id}: {e}")
        return render_template_string(detail_html, movie=None, get_active_ads=get_active_ads)

@app.route('/admin', methods=["GET", "POST"])
@requires_auth
def admin():
    if request.method == "POST":
        # ... (existing admin post handling remains unchanged) ...
        pass

    # --- GET request handling (Modified for search) ---
    admin_query = request.args.get('q') # Get the search query from URL

    if admin_query:
        # Search content by title (case-insensitive regex)
        all_content = list(movies.find({"title": {"$regex": admin_query, "$options": "i"}}).sort('_id', -1))
    else:
        # If no search query, fetch all content (as before)
        all_content = list(movies.find().sort('_id', -1))
    
    # Convert ObjectIds to string for template
    for content in all_content:
        content['_id'] = str(content['_id']) 

    return render_template_string(admin_html, movies=all_content, admin_query=admin_query)

@app.route('/edit_movie/<movie_id>', methods=["GET", "POST"])
@requires_auth
def edit_movie(movie_id):
    # ... (existing edit_movie implementation remains unchanged) ...
    pass

@app.route('/delete_movie/<movie_id>')
@requires_auth
def delete_movie(movie_id):
    # ... (existing delete_movie implementation remains unchanged) ...
    pass

@app.route('/trending_movies')
def trending_movies():
    # ... (existing trending_movies implementation remains unchanged) ...
    pass

@app.route('/movies_only')
def movies_only():
    # ... (existing movies_only implementation remains unchanged) ...
    pass

@app.route('/webseries')
def webseries():
    # ... (existing webseries implementation remains unchanged) ...
    pass

@app.route('/coming_soon')
def coming_soon():
    # ... (existing coming_soon implementation remains unchanged) ...
    pass

# --- Ad management routes ---
@app.route('/ad_admin', methods=["GET", "POST"])
@requires_auth
def ad_admin():
    if request.method == "POST":
        # ... (existing ad_admin post handling remains unchanged) ...
        pass
    
    # GET request: show all ads
    all_ads = list(ads.find().sort('created_at', -1))
    for ad in all_ads:
        ad['_id'] = str(ad['_id'])
    return render_template_string(ad_admin_html, ads=all_ads)

@app.route('/edit_ad/<ad_id>', methods=["GET", "POST"])
@requires_auth
def edit_ad(ad_id):
    # ... (existing edit_ad implementation remains unchanged) ...
    pass

@app.route('/delete_ad/<ad_id>')
@requires_auth
def delete_ad(ad_id):
    # ... (existing delete_ad implementation remains unchanged) ...
    pass

# --- New ad provider routes ---
@app.route('/ad_providers', methods=["GET"])
@requires_auth
def ad_providers():
    providers = list(ad_providers.find().sort("priority", 1))
    for p in providers:
        p['_id'] = str(p['_id'])
    return render_template_string(ad_providers_html, providers=providers)

@app.route('/edit_provider/<provider_id>', methods=["GET"])
@requires_auth
def edit_provider(provider_id):
    try:
        provider = ad_providers.find_one({"_id": ObjectId(provider_id)})
        if provider:
            provider['_id'] = str(provider['_id'])
            providers = list(ad_providers.find().sort("priority", 1))
            for p in providers:
                p['_id'] = str(p['_id'])
            return render_template_string(ad_providers_html, providers=providers, provider=provider)
        return redirect(url_for('ad_providers'))
    except Exception as e:
        print(f"Error fetching provider: {e}")
        return redirect(url_for('ad_providers'))

@app.route('/save_provider', methods=["POST"])
@requires_auth
def save_provider():
    try:
        provider_id = request.form.get("provider_id")
        provider_data = {
            "name": request.form.get("provider_name"),
            "api_endpoint": request.form.get("api_endpoint"),
            "api_key": request.form.get("api_key"),
            "ad_formats": request.form.getlist("ad_formats"),
            "priority": int(request.form.get("priority")),
            "is_active": request.form.get("is_active") == "true"
        }
        
        if provider_id:
            ad_providers.update_one(
                {"_id": ObjectId(provider_id)},
                {"$set": provider_data}
            )
        else:
            ad_providers.insert_one(provider_data)
        
        return redirect(url_for('ad_providers'))
    except Exception as e:
        print(f"Error saving provider: {e}")
        return redirect(url_for('ad_providers'))

@app.route('/delete_provider/<provider_id>')
@requires_auth
def delete_provider(provider_id):
    try:
        ad_providers.delete_one({"_id": ObjectId(provider_id)})
    except Exception as e:
        print(f"Error deleting provider: {e}")
    return redirect(url_for('ad_providers'))

@app.route('/logout')
@requires_auth
def logout():
    return Response(
        'Logged out successfully. Please close your browser.', 401,
        {'WWW-Authenticate': 'Basic realm="Logged Out"'})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
