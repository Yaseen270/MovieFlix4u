from flask import Flask, render_template_string, request, redirect, url_for, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests, os
from functools import wraps
from dotenv import load_dotenv

# .env ফাইল থেকে এনভায়রনমেন্ট ভেরিয়েবল লোড করুন (শুধুমাত্র লোকাল ডেভেলপমেন্টের জন্য)
load_dotenv()

app = Flask(__name__)

# Environment variables for MongoDB URI and TMDb API Key
MONGO_URI = os.getenv("MONGO_URI")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# --- অ্যাডমিন অথেন্টিকেশনের জন্য নতুন ভেরিয়েবল ও ফাংশন ---
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin") # এনভায়রনমেন্ট ভেরিয়েবল থেকে ইউজারনেম নিন, ডিফল্ট 'admin'
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password") # এনভায়রনমেন্ট ভেরিয়েবল থেকে পাসওয়ার্ড নিন, ডিফল্ট 'password'

def check_auth(username, password):
    """ইউজারনেম ও পাসওয়ার্ড সঠিক কিনা তা যাচাই করে।"""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    """অথেন্টিকেশন ব্যর্থ হলে 401 রেসপন্স পাঠায়।"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    """এই ডেকোরেটরটি রুট ফাংশনে অথেন্টিকেশন চেক করে।"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated
# --- অথেন্টিকেশন সংক্রান্ত পরিবর্তন শেষ ---

# Check if environment variables are set
if not MONGO_URI:
    print("Error: MONGO_URI environment variable not set. Exiting.")
    exit(1)
if not TMDB_API_KEY:
    print("Error: TMDB_API_KEY environment variable not set. Exiting.")
    exit(1)

# Database connection
try:
    client = MongoClient(MONGO_URI)
    db = client["movie_db"]
    movies = db["movies"]
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}. Exiting.")
    exit(1)

# TMDb Genre Map (for converting genre IDs to names) - অপরিবর্তিত
TMDb_Genre_Map = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    99: "Documentary", 18: "Drama", 10402: "Music", 9648: "Mystery",
    10749: "Romance", 878: "Science Fiction", 10770: "TV Movie", 53: "Thriller",
    10752: "War", 37: "Western", 10751: "Family", 14: "Fantasy", 36: "History"
}

# --- START OF index_html TEMPLATE --- (কোন পরিবর্তন নেই)
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
    header h1 { font-size: 20px; }
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


# --- START OF detail_html TEMPLATE --- (কোন পরিবর্তন নেই)
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


# --- START OF admin_html TEMPLATE --- (সার্চ ফর্ম সহ নতুন কোড)
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
    input[type="checkbox"] { /* Style for checkbox */
        width: auto; /* Revert width for checkbox */
        margin-right: 10px;
    }
    textarea {
        resize: vertical; /* Allow vertical resizing of textarea */
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
  </style>
</head>
<body>
  <h2>Add New Movie</h2>
  <form method="post">
    <div class="form-group">
        <label for="title">Movie/Series Title:</label>
        <input type="text" name="title" id="title" placeholder="Movie or Series Title" required />
    </div>

    <div class="form-group">
        <label for="content_type">Content Type:</label>
        <select name="content_type" id="content_type" onchange="toggleEpisodeFields()">
            <option value="movie">Movie</option>
            <option value="series">TV Series / Web Series</option>
        </select>
    </div>

    <div class="form-group" id="movie_download_links_group"> {# Group for movie links #}
        <label>Download Links (only paste URL):</label>
        <div class="link-input-group">
            <p>480p Download Link [Approx. 590MB]:</p>
            <input type="url" name="link_480p" placeholder="Enter 480p download link" />
        </div>
        <div class="link-input-group">
            <p>720p Download Link [Approx. 1.4GB]:</p>
            <input type="url" name="link_720p" placeholder="Enter 720p download link" />
        </div>
        <div class="link-input-group">
            <p>1080p Download Link [Approx. 2.9GB]:</p>
            <input type="url" name="link_1080p" placeholder="Enter 1080p download link" />
        </div>
    </div>

    <div id="episode_fields" style="display: none;"> {# Initially hidden for series episodes #}
        <h3>Episodes</h3>
        <div id="episodes_container">
            {# Episodes will be dynamically added here by JavaScript #}
        </div>
        <button type="button" onclick="addEpisodeField()">Add New Episode</button>
    </div>


    <div class="form-group">
        <label for="quality">Quality Tag (e.g., HD, Hindi Dubbed):</label>
        <input type="text" name="quality" id="quality" placeholder="Quality tag" />
    </div>

    <div class="form-group">
        <label for="top_label">Poster Top Label (Optional, e.g., Special Offer, New):</label>
        <input type="text" name="top_label" id="top_label" placeholder="Custom label on poster top" />
    </div>

    <div class="form-group">
        <input type="checkbox" name="is_trending" id="is_trending" value="true">
        <label for="is_trending" style="display: inline-block;">Is Trending?</label>
    </div>

    <div class="form-group">
        <input type="checkbox" name="is_coming_soon" id="is_coming_soon" value="true">
        <label for="is_coming_soon" style="display: inline-block;">Is Coming Soon?</label>
    </div>

    <div class="form-group">
        <label for="overview">Overview (Optional - used if TMDb info not found):</label>
        <textarea name="overview" id="overview" rows="5" placeholder="Enter movie/series overview or synopsis"></textarea>
    </div>

    <div class="form-group">
        <label for="poster_url">Poster URL (Optional - direct image link, used if TMDb info not found):</label>
        <input type="url" name="poster_url" id="poster_url" placeholder="e.g., https://example.com/poster.jpg" />
    </div>

    <div class="form-group">
        <label for="year">Release Year (Optional - used if TMDb info not found):</label>
        <input type="text" name="year" id="year" placeholder="e.g., 2023" />
    </div>

    <div class="form-group">
        <label for="original_language">Original Language (Optional - used if TMDb info not found):</label>
        <input type="text" name="original_language" id="original_language" placeholder="e.g., Bengali, English" />
    </div>

    <div class="form-group">
        <label for="genres">Genres (Optional - comma-separated, used if TMDb info not found):</label>
        <input type="text" name="genres" id="genres" placeholder="e.g., Action, Drama, Thriller" />
    </div>
    
    <button type="submit">Add Content</button>
  </form>

  <h2 style="margin-top: 40px;">Search Content</h2> {# New Search Section #}
  <form method="GET" action="{{ url_for('admin') }}">
    <div class="form-group">
      <label for="admin_search_query">Search by Title:</label>
      <input type="search" name="q" id="admin_search_query" placeholder="Search content by title..." value="{{ admin_query|default('') }}" />
    </div>
    <button type="submit">Search</button>
  </form>

  <hr>

  <h2>Manage Existing Content {% if admin_query %}for "{{ admin_query }}"{% endif %}</h2> {# Updated Heading #}
  <div class="movie-list-container">
    {% if movies %}
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Type</th>
          <th>Quality</th>
          <th>Trending</th>
          <th>Coming Soon</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for movie in movies %}
        <tr>
          <td>{{ movie.title }}</td>
          <td>{{ movie.type | title }}</td>
          <td>{% if movie.quality %}{{ movie.quality }}{% else %}N/A{% endif %}</td> {# Handle cases where quality might be None #}
          <td>{% if movie.quality == 'TRENDING' %}Yes{% else %}No{% endif %}</td>
          <td>{% if movie.is_coming_soon %}Yes{% else %}No{% endif %}</td>
          <td class="action-buttons">
            <a href="{{ url_for('edit_movie', movie_id=movie._id) }}" class="edit-btn">Edit</a>
            <button class="delete-btn" onclick="confirmDelete('{{ movie._id }}', '{{ movie.title }}')">Delete</button>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p style="text-align:center; color:#999;">No content found in the database.</p>
    {% endif %}
  </div>

  <script>
    function confirmDelete(movieId, movieTitle) {
      if (confirm('Are you sure you want to delete "' + movieTitle + '"?')) {
        window.location.href = '/delete_movie/' + movieId;
      }
    }

    function toggleEpisodeFields() {
        var contentType = document.getElementById('content_type').value;
        var episodeFields = document.getElementById('episode_fields');
        var movieDownloadLinksGroup = document.getElementById('movie_download_links_group');
        
        if (contentType === 'series') {
            episodeFields.style.display = 'block';
            if (movieDownloadLinksGroup) {
                movieDownloadLinksGroup.style.display = 'none';
            }
        } else {
            episodeFields.style.display = 'none';
            if (movieDownloadLinksGroup) {
                movieDownloadLinksGroup.style.display = 'block';
            }
        }
    }

    function addEpisodeField(episode = {}) {
        const container = document.getElementById('episodes_container');
        const newEpisodeDiv = document.createElement('div');
        newEpisodeDiv.className = 'episode-item';
        newEpisodeDiv.style.cssText = 'border: 1px solid #444; padding: 10px; margin-bottom: 10px; border-radius: 5px;';
        
        const episodeNumber = episode.episode_number || '';
        const episodeTitle = episode.title || '';
        const episodeOverview = episode.overview || '';
        const link480p = (episode.links && episode.links.find(l => l.quality === '480p')) ? episode.links.find(l => l.quality === '480p').url : '';
        const link720p = (episode.links && episode.links.find(l => l.quality === '720p')) ? episode.links.find(l => l.quality === '720p').url : '';
        const link1080p = (episode.links && episode.links.find(l => l.quality === '1080p')) ? episode.links.find(l => l.quality === '1080p').url : '';

        newEpisodeDiv.innerHTML = `
            <div class="form-group">
                <label>Episode Number:</label>
                <input type="number" name="episode_number[]" value="${episodeNumber}" required />
            </div>
            <div class="form-group">
                <label>Episode Title:</label>
                <input type="text" name="episode_title[]" value="${episodeTitle}" placeholder="e.g., Episode 1: The Beginning" required />
            </div>
            <div class="form-group">
                <label>Episode Overview (Optional):</label>
                <textarea name="episode_overview[]" rows="3" placeholder="Overview for this episode">${episodeOverview}</textarea>
            </div>
            <div class="link-input-group">
                <p>480p Link:</p>
                <input type="url" name="episode_link_480p[]" value="${link480p}" placeholder="Enter 480p download link" />
            </div>
            <div class="link-input-group">
                <p>720p Link:</p>
                <input type="url" name="episode_link_720p[]" value="${link720p}" placeholder="Enter 720p download link" />
            </div>
            <div class="link-input-group">
                <p>1080p Link:</p>
                <input type="url" name="episode_link_1080p[]" value="${link1080p}" placeholder="Enter 1080p download link" />
            </div>
            <button type="button" onclick="removeEpisode(this)" class="delete-btn" style="background: #e44d26;">Remove Episode</button>
        `;
        container.appendChild(newEpisodeDiv);
    }

    function removeEpisode(button) {
        button.closest('.episode-item').remove();
    }

    // Call on page load to set initial state
    document.addEventListener('DOMContentLoaded', toggleEpisodeFields);
  </script>
</body>
</html>
"""
# --- END OF admin_html TEMPLATE ---


# --- START OF edit_html TEMPLATE --- (কোন পরিবর্তন নেই)
edit_html = """
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
    <div class="form-group">
        <label for="title">Movie/Series Title:</label>
        <input type="text" name="title" id="title" placeholder="Movie or Series Title" value="{{ movie.title }}" required />
    </div>

    <div class="form-group">
        <label for="content_type">Content Type:</label>
        <select name="content_type" id="content_type" onchange="toggleEpisodeFields()">
            <option value="movie" {% if movie.type == 'movie' %}selected{% endif %}>Movie</option>
            <option value="series" {% if movie.type == 'series' %}selected{% endif %}>TV Series / Web Series</option>
        </select>
    </div>

    <div class="form-group" id="movie_download_links_group"> {# Group for movie links #}
        <label>Download Links (only paste URL):</label>
        <div class="link-input-group">
            <p>480p Download Link [Approx. 590MB]:</p>
            <input type="url" name="link_480p" placeholder="Enter 480p download link" value="{% for link in movie.links %}{% if link.quality == '480p' %}{{ link.url }}{% endif %}{% endfor %}" />
        </div>
        <div class="link-input-group">
            <p>720p Download Link [Approx. 1.4GB]:</p>
            <input type="url" name="link_720p" placeholder="Enter 720p download link" value="{% for link in movie.links %}{% if link.quality == '720p' %}{{ link.url }}{% endif %}{% endfor %}" />
        </div>
        <div class="link-input-group">
            <p>1080p Download Link [Approx. 2.9GB]:</p>
            <input type="url" name="link_1080p" placeholder="Enter 1080p download link" value="{% for link in movie.links %}{% if link.quality == '1080p' %}{{ link.url }}{% endif %}{% endfor %}" />
        </div>
    </div>

    <div id="episode_fields" style="display: none;"> {# Initially hidden for series episodes #}
        <h3>Episodes</h3>
        <div id="episodes_container">
            {# Existing episodes will be loaded here in edit mode #}
            {% if movie.type == 'series' and movie.episodes %}
                {% for episode in movie.episodes %}
                    <div class="episode-item" style="border: 1px solid #444; padding: 10px; margin-bottom: 10px; border-radius: 5px;">
                        <div class="form-group">
                            <label>Episode Number:</label>
                            <input type="number" name="episode_number[]" value="{{ episode.episode_number }}" required />
                        </div>
                        <div class="form-group">
                            <label>Episode Title:</label>
                            <input type="text" name="episode_title[]" value="{{ episode.title }}" placeholder="e.g., Episode 1: The Beginning" required />
                        </div>
                        <div class="form-group">
                            <label>Episode Overview (Optional):</label>
                            <textarea name="episode_overview[]" rows="3" placeholder="Overview for this episode">{{ episode.overview }}</textarea>
                        </div>
                        <div class="link-input-group">
                            <p>480p Link:</p>
                            <input type="url" name="episode_link_480p[]" value="{% for link in episode.links %}{% if link.quality == '480p' %}{{ link.url }}{% endif %}{% endfor %}" placeholder="Enter 480p download link" />
                        </div>
                        <div class="link-input-group">
                            <p>720p Link:</p>
                            <input type="url" name="episode_link_720p[]" value="{% for link in episode.links %}{% if link.quality == '720p' %}{{ link.url }}{% endif %}{% endfor %}" placeholder="Enter 720p download link" />
                        </div>
                        <div class="link-input-group">
                            <p>1080p Link:</p>
                            <input type="url" name="episode_link_1080p[]" value="{% for link in episode.links %}{% if link.quality == '1080p' %}{{ link.url }}{% endif %}{% endfor %}" placeholder="Enter 1080p download link" />
                        </div>
                        <button type="button" onclick="removeEpisode(this)" class="delete-btn" style="background: #e44d26;">Remove Episode</button>
                    </div>
                {% endfor %}
            {% endif %}
        </div>
        <button type="button" onclick="addEpisodeField()">Add New Episode</button>
    </div>


    <div class="form-group">
        <label for="quality">Quality Tag (e.g., HD, Hindi Dubbed):</label>
        <input type="text" name="quality" id="quality" placeholder="Quality tag" value="{{ movie.quality }}" />
    </div>

    <div class="form-group">
        <label for="top_label">Poster Top Label (Optional, e.g., Special Offer, New):</label>
        <input type="text" name="top_label" id="top_label" placeholder="Custom label on poster top" value="{{ movie.top_label }}" />
    </div>

    <div class="form-group">
        <input type="checkbox" name="is_trending" id="is_trending" value="true" {% if movie.quality == 'TRENDING' %}checked{% endif %}>
        <label for="is_trending" style="display: inline-block;">Is Trending?</label>
    </div>

    <div class="form-group">
        <input type="checkbox" name="is_coming_soon" id="is_coming_soon" value="true" {% if movie.is_coming_soon %}checked{% endif %}>
        <label for="is_coming_soon" style="display: inline-block;">Is Coming Soon?</label>
    </div>

    <div class="form-group">
        <label for="overview">Overview (Optional - used if TMDb info not found):</label>
        <textarea name="overview" id="overview" rows="5" placeholder="Enter movie/series overview or synopsis">{{ movie.overview }}</textarea>
    </div>

    <div class="form-group">
        <label for="poster_url">Poster URL (Optional - direct image link, used if TMDb info not found):</label>
        <input type="url" name="poster_url" id="poster_url" placeholder="e.g., https://example.com/poster.jpg" value="{{ movie.poster }}" />
    </div>

    <div class="form-group">
        <label for="year">Release Year (Optional - used if TMDb info not found):</label>
        <input type="text" name="year" id="year" placeholder="e.g., 2023" value="{{ movie.year }}" />
    </div>

    <div class="form-group">
        <label for="original_language">Original Language (Optional - used if TMDb info not found):</label>
        <input type="text" name="original_language" id="original_language" placeholder="e.g., Bengali, English" value="{{ movie.original_language }}" />
    </div>

    <div class="form-group">
        <label for="genres">Genres (Optional - comma-separated, used if TMDb info not found):</label>
        <input type="text" name="genres" id="genres" placeholder="e.g., Action, Drama, Thriller" value="{{ movie.genres | join(', ') }}" />
    </div>
    
    <button type="submit">Update Content</button>
  </form>
  <script>
    function toggleEpisodeFields() {
        var contentType = document.getElementById('content_type').value;
        var episodeFields = document.getElementById('episode_fields');
        var movieDownloadLinksGroup = document.getElementById('movie_download_links_group');
        
        if (contentType === 'series') {
            episodeFields.style.display = 'block';
            if (movieDownloadLinksGroup) {
                movieDownloadLinksGroup.style.display = 'none';
            }
        } else {
            episodeFields.style.display = 'none';
            if (movieDownloadLinksGroup) {
                movieDownloadLinksGroup.style.display = 'block';
            }
        }
    }

    function addEpisodeField(episode = {}) {
        const container = document.getElementById('episodes_container');
        const newEpisodeDiv = document.createElement('div');
        newEpisodeDiv.className = 'episode-item';
        newEpisodeDiv.style.cssText = 'border: 1px solid #444; padding: 10px; margin-bottom: 10px; border-radius: 5px;';
        
        const episodeNumber = episode.episode_number || '';
        const episodeTitle = episode.title || '';
        const episodeOverview = episode.overview || '';
        const link480p = (episode.links && episode.links.find(l => l.quality === '480p')) ? episode.links.find(l => l.quality === '480p').url : '';
        const link720p = (episode.links && episode.links.find(l => l.quality === '720p')) ? episode.links.find(l => l.quality === '720p').url : '';
        const link1080p = (episode.links && episode.links.find(l => l.quality === '1080p')) ? episode.links.find(l => l.quality === '1080p').url : '';

        newEpisodeDiv.innerHTML = `
            <div class="form-group">
                <label>Episode Number:</label>
                <input type="number" name="episode_number[]" value="${episodeNumber}" required />
            </div>
            <div class="form-group">
                <label>Episode Title:</label>
                <input type="text" name="episode_title[]" value="${episodeTitle}" placeholder="e.g., Episode 1: The Beginning" required />
            </div>
            <div class="form-group">
                <label>Episode Overview (Optional):</label>
                <textarea name="episode_overview[]" rows="3" placeholder="Overview for this episode">${episodeOverview}</textarea>
            </div>
            <div class="link-input-group">
                <p>480p Link:</p>
                <input type="url" name="episode_link_480p[]" value="${link480p}" placeholder="Enter 480p download link" />
            </div>
            <div class="link-input-group">
                <p>720p Link:</p>
                <input type="url" name="episode_link_720p[]" value="${link720p}" placeholder="Enter 720p download link" />
            </div>
            <div class="link-input-group">
                <p>1080p Link:</p>
                <input type="url" name="episode_link_1080p[]" value="${link1080p}" placeholder="Enter 1080p download link" />
            </div>
            <button type="button" onclick="removeEpisode(this)" class="delete-btn" style="background: #e44d26;">Remove Episode</button>
        `;
        container.appendChild(newEpisodeDiv);
    }

    function removeEpisode(button) {
        button.closest('.episode-item').remove();
    }

    // Call on page load to set initial state based on current movie type
    document.addEventListener('DOMContentLoaded', function() {
        toggleEpisodeFields(); // Set initial visibility
        // If it's an edit page for a series, ensure episode fields are visible and loaded
        var movieType = document.getElementById('content_type').value;
        if (movieType === 'series' && typeof movie !== 'undefined' && movie.episodes) {
             // Episodes are already loaded by Jinja in the template, no need to add dynamically
             // unless we want to allow adding *new* empty fields on load for a fresh series.
             // For existing series, the current setup where Jinja renders them is fine.
        }
    });
  </script>
</body>
</html>
"""
# --- END OF edit_html TEMPLATE ---


@app.route('/')
def home():
    query = request.args.get('q')
    
    movies_list = []
    trending_movies_list = []
    latest_movies_list = []
    latest_series_list = []
    coming_soon_movies_list = []

    # is_full_page_list = False for the homepage
    is_full_page_list = False

    if query:
        # Search functionality remains the same
        result = movies.find({"title": {"$regex": query, "$options": "i"}})
        movies_list = list(result)
        is_full_page_list = True # Search results should also be vertical
    else:
        # Fetch data for each category on the homepage with a limit of 6
        # Trending (quality == 'TRENDING')
        trending_movies_result = movies.find({"quality": "TRENDING"}).sort('_id', -1).limit(6)
        trending_movies_list = list(trending_movies_result)

        # Latest Movies (type == 'movie', not trending, not coming soon)
        latest_movies_result = movies.find({
            "type": "movie",
            "quality": {"$ne": "TRENDING"},
            "is_coming_soon": {"$ne": True}
        }).sort('_id', -1).limit(6)
        latest_movies_list = list(latest_movies_result)

        # Latest Web Series (type == 'series', not trending, not coming soon)
        latest_series_result = movies.find({
            "type": "series",
            "quality": {"$ne": "TRENDING"},
            "is_coming_soon": {"$ne": True}
        }).sort('_id', -1).limit(6)
        latest_series_list = list(latest_series_result)

        # Coming Soon (is_coming_soon == True)
        coming_soon_result = movies.find({"is_coming_soon": True}).sort('_id', -1).limit(6)
        coming_soon_movies_list = list(coming_soon_result)

    # Convert ObjectIds to strings for all fetched lists
    for m in movies_list + trending_movies_list + latest_movies_list + latest_series_list + coming_soon_movies_list:
        m['_id'] = str(m['_id']) 

    return render_template_string(
        index_html, 
        movies=movies_list, # Only used for search results or full page lists
        query=query,
        trending_movies=trending_movies_list,
        latest_movies=latest_movies_list,
        latest_series=latest_series_list,
        coming_soon_movies=coming_soon_movies_list,
        is_full_page_list=is_full_page_list # Pass this flag to the template
    )

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if movie:
            movie['_id'] = str(movie['_id'])
            
            # Fetch additional details from TMDb if API key is available
            # Only fetch if tmdb_id is not already present or if the existing poster/overview are default values.
            # AND if it's a movie (TMDb episode details are more complex)
            should_fetch_tmdb = TMDB_API_KEY and (not movie.get("tmdb_id") or movie.get("overview") == "No overview available." or not movie.get("poster")) and movie.get("type") == "movie"

            if should_fetch_tmdb:
                tmdb_id = movie.get("tmdb_id") 
                
                # If TMDb ID is not stored, search by title first
                if not tmdb_id:
                    # Decide whether to search as movie or tv based on 'type' field
                    tmdb_search_type = "movie" if movie.get("type") == "movie" else "tv" # Will only be 'movie' due to should_fetch_tmdb
                    search_url = f"https://api.themoviedb.org/3/search/{tmdb_search_type}?api_key={TMDB_API_KEY}&query={movie['title']}"
                    try:
                        search_res = requests.get(search_url, timeout=5).json()
                        if search_res and "results" in search_res and search_res["results"]:
                            tmdb_id = search_res["results"][0].get("id")
                            # Update the movie in DB with tmdb_id for future faster access
                            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": {"tmdb_id": tmdb_id}})
                        else:
                            print(f"No search results found on TMDb for title: {movie['title']} ({tmdb_search_type})")
                            tmdb_id = None # Ensure tmdb_id is None if no search results
                    except requests.exceptions.RequestException as e:
                        print(f"Error connecting to TMDb API for search '{movie['title']}': {e}")
                        tmdb_id = None
                    except Exception as e:
                        print(f"An unexpected error occurred during TMDb search: {e}")
                        tmdb_id = None

                # If TMDb ID is found (either from DB or search), fetch full details
                if tmdb_id:
                    tmdb_detail_type = "movie" # Always movie if should_fetch_tmdb is true
                    tmdb_detail_url = f"https://api.themoviedb.org/3/{tmdb_detail_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
                    try:
                        res = requests.get(tmdb_detail_url, timeout=5).json()
                        if res:
                            # Only update if TMDb provides a better value AND manual data wasn't provided
                            if movie.get("overview") == "No overview available." and res.get("overview"):
                                movie["overview"] = res.get("overview")
                            if not movie.get("poster") and res.get("poster_path"):
                                movie["poster"] = f"https://image.tmdb.org/t/p/w500{res['poster_path']}"
                            
                            release_date = res.get("release_date") # For movies
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
                            if (not movie.get("genres") or movie["genres"] == []) and genres_names: # Only update if TMDb provides genres and no manual genres
                                movie["genres"] = genres_names

                            # Persist TMDb fetched data to DB
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

        return render_template_string(detail_html, movie=movie)
    except Exception as e:
        print(f"Error fetching movie detail for ID {movie_id}: {e}")
        return render_template_string(detail_html, movie=None)

@app.route('/admin', methods=["GET", "POST"])
@requires_auth # অথেন্টিকেশন ডেকোরেটর যোগ করা হয়েছে
def admin():
    if request.method == "POST":
        title = request.form.get("title")
        content_type = request.form.get("content_type", "movie") # New: 'movie' or 'series'
        quality_tag = request.form.get("quality", "").upper()
        
        # Get manual inputs
        manual_overview = request.form.get("overview")
        manual_poster_url = request.form.get("poster_url")
        manual_year = request.form.get("year")
        manual_original_language = request.form.get("original_language")
        manual_genres_str = request.form.get("genres")
        manual_top_label = request.form.get("top_label") # Get custom top label
        is_trending = request.form.get("is_trending") == "true" # New: Checkbox for trending
        is_coming_soon = request.form.get("is_coming_soon") == "true" # New: Checkbox for coming soon

        # Process manual genres (comma-separated string to list)
        manual_genres_list = [g.strip() for g in manual_genres_str.split(',') if g.strip()] if manual_genres_str else []

        # If is_trending is true, force quality to 'TRENDING'
        if is_trending:
            quality_tag = "TRENDING"

        movie_data = {
            "title": title,
            "quality": quality_tag,
            "type": content_type, # Use selected content type
            "overview": manual_overview if manual_overview else "No overview available.",
            "poster": manual_poster_url if manual_poster_url else "",
            "year": manual_year if manual_year else "N/A",
            "release_date": manual_year if manual_year else "N/A", 
            "vote_average": None,
            "original_language": manual_original_language if manual_original_language else "N/A",
            "genres": manual_genres_list,
            "tmdb_id": None,
            "top_label": manual_top_label if manual_top_label else "",
            "is_coming_soon": is_coming_soon # Store coming soon status
        }

        # Handle download links based on content type
        if content_type == "movie":
            links_list = []
            link_480p = request.form.get("link_480p")
            if link_480p:
                links_list.append({"quality": "480p", "size": "590MB", "url": link_480p})
            link_720p = request.form.get("link_720p")
            if link_720p:
                links_list.append({"quality": "720p", "size": "1.4GB", "url": link_720p})
            link_1080p = request.form.get("link_1080p")
            if link_1080p:
                links_list.append({"quality": "1080p", "size": "2.9GB", "url": link_1080p})
            movie_data["links"] = links_list
        else: # content_type == "series"
            episodes_list = []
            episode_numbers = request.form.getlist('episode_number[]')
            episode_titles = request.form.getlist('episode_title[]')
            episode_overviews = request.form.getlist('episode_overview[]')
            episode_link_480ps = request.form.getlist('episode_link_480p[]')
            episode_link_720ps = request.form.getlist('episode_link_720p[]')
            episode_link_1080ps = request.form.getlist('episode_link_1080p[]')

            for i in range(len(episode_numbers)):
                episode_links = []
                if episode_link_480ps and episode_link_480ps[i]:
                    episode_links.append({"quality": "480p", "size": "590MB", "url": episode_link_480ps[i]})
                if episode_link_720ps and episode_link_720ps[i]:
                    episode_links.append({"quality": "720p", "size": "1.4GB", "url": episode_link_720ps[i]})
                if episode_link_1080ps and episode_link_1080ps[i]:
                    episode_links.append({"quality": "1080p", "size": "2.9GB", "url": episode_link_1080ps[i]})
                
                episodes_list.append({
                    "episode_number": int(episode_numbers[i]) if episode_numbers[i] else 0,
                    "title": episode_titles[i] if episode_titles else "",
                    "overview": episode_overviews[i] if episode_overviews else "",
                    "links": episode_links
                })
            movie_data["episodes"] = episodes_list

        # Try to fetch from TMDb only if no manual poster or overview was provided
        # And if it's a movie, TMDb series episode fetching is more complex and not implemented here
        if TMDB_API_KEY and content_type == "movie" and (not manual_poster_url and not manual_overview or movie_data["overview"] == "No overview available." or not movie_data["poster"]):
            tmdb_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={title}"
            try:
                res = requests.get(tmdb_url, timeout=5).json()
                if res and "results" in res and res["results"]:
                    data = res["results"][0]
                    # Overwrite only if TMDb provides a value and manual data wasn't explicitly provided
                    if not manual_overview and data.get("overview"):
                        movie_data["overview"] = data.get("overview")
                    if not manual_poster_url and data.get("poster_path"):
                        movie_data["poster"] = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
                    
                    release_date = data.get("release_date")
                    if not manual_year and release_date:
                        movie_data["year"] = release_date[:4]
                        movie_data["release_date"] = release_date
                    
                    movie_data["vote_average"] = data.get("vote_average", movie_data["vote_average"])
                    if not manual_original_language and data.get("original_language"):
                        movie_data["original_language"] = data.get("original_language")
                    
                    genres_names = []
                    for genre_id in data.get("genre_ids", []):
                        if genre_id in TMDb_Genre_Map:
                            genres_names.append(TMDb_Genre_Map[genre_id])
                    if not manual_genres_list and genres_names: # Only update genres if TMDb provides them AND no manual genres
                        movie_data["genres"] = genres_names
                    
                    movie_data["tmdb_id"] = data.get("id")
                else:
                    print(f"No results found on TMDb for title: {title} (movie)")
            except requests.exceptions.RequestException as e:
                print(f"Error connecting to TMDb API for '{title}': {e}")
            except Exception as e:
                print(f"An unexpected error occurred while fetching TMDb data: {e}")
        else:
            print("Skipping TMDb API call (not a movie, no key, or manual poster/overview provided).")

        try:
            movies.insert_one(movie_data)
            print(f"Content '{movie_data['title']}' added successfully to MovieZone!")
            return redirect(url_for('admin')) # Redirect to admin after POST
        except Exception as e:
            print(f"Error inserting content into MongoDB: {e}")
            return redirect(url_for('admin'))

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
@requires_auth # অথেন্টিকেশন ডেকোরেটর যোগ করা হয়েছে
def edit_movie(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie:
            return "Movie not found!", 404

        if request.method == "POST":
            # Extract updated data from form
            title = request.form.get("title")
            content_type = request.form.get("content_type", "movie")
            quality_tag = request.form.get("quality", "").upper()
            
            manual_overview = request.form.get("overview")
            manual_poster_url = request.form.get("poster_url")
            manual_year = request.form.get("year")
            manual_original_language = request.form.get("original_language")
            manual_genres_str = request.form.get("genres")
            manual_top_label = request.form.get("top_label")
            is_trending = request.form.get("is_trending") == "true"
            is_coming_soon = request.form.get("is_coming_soon") == "true"

            manual_genres_list = [g.strip() for g in manual_genres_str.split(',') if g.strip()] if manual_genres_str else []

            if is_trending:
                quality_tag = "TRENDING"
            
            # Prepare updated data for MongoDB
            updated_data = {
                "title": title,
                "quality": quality_tag,
                "type": content_type,
                "overview": manual_overview if manual_overview else "No overview available.",
                "poster": manual_poster_url if manual_poster_url else "",
                "year": manual_year if manual_year else "N/A",
                "release_date": manual_year if manual_year else "N/A", # Assuming release_date is same as year if manually entered
                "original_language": manual_original_language if manual_original_language else "N/A",
                "genres": manual_genres_list,
                "top_label": manual_top_label if manual_top_label else "",
                "is_coming_soon": is_coming_soon
            }

            # Handle download links based on content type
            if content_type == "movie":
                links_list = []
                link_480p = request.form.get("link_480p")
                if link_480p:
                    links_list.append({"quality": "480p", "size": "590MB", "url": link_480p})
                link_720p = request.form.get("link_720p")
                if link_720p:
                    links_list.append({"quality": "720p", "size": "1.4GB", "url": link_720p})
                link_1080p = request.form.get("link_1080p")
                if link_1080p:
                    links_list.append({"quality": "1080p", "size": "2.9GB", "url": link_1080p})
                updated_data["links"] = links_list
                # Remove episodes if present for a movie
                if "episodes" in movie:
                    movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"episodes": ""}})
            else: # content_type == "series"
                episodes_list = []
                episode_numbers = request.form.getlist('episode_number[]')
                episode_titles = request.form.getlist('episode_title[]')
                episode_overviews = request.form.getlist('episode_overview[]')
                episode_link_480ps = request.form.getlist('episode_link_480p[]')
                episode_link_720ps = request.form.getlist('episode_link_720p[]')
                episode_link_1080ps = request.form.getlist('episode_link_1080p[]')

                for i in range(len(episode_numbers)):
                    episode_links = []
                    if episode_link_480ps and episode_link_480ps[i]:
                        episode_links.append({"quality": "480p", "size": "590MB", "url": episode_link_480ps[i]})
                    if episode_link_720ps and episode_link_720ps[i]:
                        episode_links.append({"quality": "720p", "size": "1.4GB", "url": episode_link_720ps[i]})
                    if episode_link_1080ps and episode_link_1080ps[i]:
                        episode_links.append({"quality": "1080p", "size": "2.9GB", "url": episode_link_1080ps[i]})
                    
                    episodes_list.append({
                        "episode_number": int(episode_numbers[i]) if episode_numbers[i] else 0,
                        "title": episode_titles[i] if episode_titles else "",
                        "overview": episode_overviews[i] if episode_overviews else "",
                        "links": episode_links
                    })
                updated_data["episodes"] = episodes_list
                # Remove top-level 'links' if present for series
                if "links" in movie:
                    movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"links": ""}})


            # If TMDb API Key is available and no manual overview/poster provided, fetch and update
            # Only for movies, as TMDb episode details are more complex
            if TMDB_API_KEY and content_type == "movie" and (not manual_poster_url and not manual_overview): # Only try to fetch if not manually overridden
                tmdb_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={title}"
                try:
                    res = requests.get(tmdb_url, timeout=5).json()
                    if res and "results" in res and res["results"]:
                        data = res["results"][0]
                        # Only update if TMDb provides a value and manual data wasn't explicitly provided
                        if not manual_overview and data.get("overview"):
                            updated_data["overview"] = data.get("overview")
                        if not manual_poster_url and data.get("poster_path"):
                            updated_data["poster"] = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
                        
                        release_date = data.get("release_date")
                        if not manual_year and release_date:
                            updated_data["year"] = release_date[:4]
                            updated_data["release_date"] = release_date
                        
                        updated_data["vote_average"] = data.get("vote_average", movie.get("vote_average")) # Keep old if TMDb doesn't provide
                        if not manual_original_language and data.get("original_language"):
                            updated_data["original_language"] = data.get("original_language")
                        
                        genres_names = []
                        for genre_id in data.get("genre_ids", []):
                            if genre_id in TMDb_Genre_Map:
                                genres_names.append(TMDb_Genre_Map[genre_id])
                        if not manual_genres_list and genres_names:
                            updated_data["genres"] = genres_names
                        
                        updated_data["tmdb_id"] = data.get("id")
                    else:
                        print(f"No results found on TMDb for title: {title} (movie) during edit.")
                except requests.exceptions.RequestException as e:
                    print(f"Error connecting to TMDb API for '{title}' during edit: {e}")
                except Exception as e:
                    print(f"An unexpected error occurred while fetching TMDb data during edit: {e}")
            else:
                print("Skipping TMDb API call (not a movie, no key, or manual poster/overview provided).")
            
            # Update the movie in MongoDB
            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": updated_data})
            print(f"Content '{title}' updated successfully!")
            return redirect(url_for('admin')) # Redirect back to admin list after update

        else: # GET request, display the form
            # Convert ObjectId to string for template
            movie['_id'] = str(movie['_id']) 
            return render_template_string(edit_html, movie=movie)

    except Exception as e:
        print(f"Error processing edit for movie ID {movie_id}: {e}")
        return "An error occurred during editing.", 500


@app.route('/delete_movie/<movie_id>')
@requires_auth # অথেন্টিকেশন ডেকোরেটর যোগ করা হয়েছে
def delete_movie(movie_id):
    try:
        # Delete the movie from MongoDB using its ObjectId
        result = movies.delete_one({"_id": ObjectId(movie_id)})
        if result.deleted_count == 1:
            print(f"Content with ID {movie_id} deleted successfully from MovieZone!")
        else:
            print(f"Content with ID {movie_id} not found in MovieZone database.")
    except Exception as e:
        print(f"Error deleting content with ID {movie_id}: {e}")
    
    return redirect(url_for('admin')) # Redirect back to the admin page


# New routes for navigation bar and specific categories
@app.route('/trending_movies')
def trending_movies():
    trending_list = list(movies.find({"quality": "TRENDING"}).sort('_id', -1))
    for m in trending_list:
        m['_id'] = str(m['_id'])
    # Pass is_full_page_list=True and use 'movies' for the list
    return render_template_string(index_html, movies=trending_list, query="Trending on MovieZone", is_full_page_list=True)

@app.route('/movies_only')
def movies_only():
    movie_list = list(movies.find({"type": "movie", "quality": {"$ne": "TRENDING"}, "is_coming_soon": {"$ne": True}}).sort('_id', -1))
    for m in movie_list:
        m['_id'] = str(m['_id'])
    # Pass is_full_page_list=True and use 'movies' for the list
    return render_template_string(index_html, movies=movie_list, query="All Movies on MovieZone", is_full_page_list=True)

@app.route('/webseries')
def webseries():
    series_list = list(movies.find({"type": "series", "quality": {"$ne": "TRENDING"}, "is_coming_soon": {"$ne": True}}).sort('_id', -1))
    for m in series_list:
        m['_id'] = str(m['_id'])
    # Pass is_full_page_list=True and use 'movies' for the list
    return render_template_string(index_html, movies=series_list, query="All Web Series on MovieZone", is_full_page_list=True)

@app.route('/coming_soon')
def coming_soon():
    coming_soon_list = list(movies.find({"is_coming_soon": True}).sort('_id', -1))
    for m in coming_soon_list:
        m['_id'] = str(m['_id'])
    # Pass is_full_page_list=True and use 'movies' for the list
    return render_template_string(index_html, movies=coming_soon_list, query="Coming Soon to MovieZone", is_full_page_list=True)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
