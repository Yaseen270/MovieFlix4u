from flask import Flask, render_template_string, request, redirect, url_for, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests, os, datetime
from functools import wraps
from dotenv import load_dotenv

# .env ফাইল থেকে এনভায়রনমেন্ট ভেরিয়েবল লোড করুন
load_dotenv()

app = Flask(__name__)

# Environment variables
MONGO_URI = os.getenv("MONGO_URI")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")

# Database connection
try:
    client = MongoClient(MONGO_URI)
    db = client["movie_db"]
    movies = db["movies"]
    ads = db["ads"]  # New ads collection
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}. Exiting.")
    exit(1)

# TMDb Genre Map
TMDb_Genre_Map = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 
    80: "Crime", 99: "Documentary", 18: "Drama", 10402: "Music", 
    9648: "Mystery", 10749: "Romance", 878: "Science Fiction", 
    10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western", 
    10751: "Family", 14: "Fantasy", 36: "History"
}

# Authentication functions
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

# Helper function to get active ads
def get_active_ads(position=None):
    query = {
        "is_active": True,
        "start_date": {"$lte": datetime.datetime.utcnow().strftime("%Y-%m-%d")},
        "end_date": {"$gte": datetime.datetime.utcnow().strftime("%Y-%m-%d")}
    }
    
    if position:
        query["position"] = position
    
    active_ads = list(ads.find(query).sort("created_at", -1))
    for ad in active_ads:
        ad['_id'] = str(ad['_id'])
    return active_ads

# --- START OF TEMPLATES ---
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>MovieZone - Your Entertainment Hub</title>
<style>
  /* Previous CSS styles remain the same */
  
  /* New Ad Styles */
  .ad-container {
    margin: 15px auto;
    max-width: 1200px;
    padding: 0 15px;
    text-align: center;
  }
  
  .ad-container.top-banner {
    margin-top: 20px;
    margin-bottom: 20px;
  }
  
  .ad-container.middle-banner {
    margin: 30px auto;
    padding: 15px 0;
    border-top: 1px solid #333;
    border-bottom: 1px solid #333;
  }
  
  .ad-container.bottom-banner {
    margin-top: 30px;
    margin-bottom: 70px;
  }
  
  .ad-container img {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
  }
  
  @media (max-width: 768px) {
    .ad-container {
      padding: 0 10px;
    }
    
    .ad-container img {
      max-height: 90px;
    }
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

<!-- Top Banner Ad -->
{% if not is_full_page_list %}
  {% set top_ads = get_active_ads('top') %}
  {% if top_ads %}
    <div class="ad-container top-banner">
      {% for ad in top_ads %}
        <a href="{{ ad.target_url }}" target="_blank" rel="noopener noreferrer">
          <img src="{{ ad.image_url }}" alt="{{ ad.title }}">
        </a>
      {% endfor %}
    </div>
  {% endif %}
{% endif %}

<main>
  <!-- Previous main content remains the same -->
</main>

<!-- Bottom Banner Ad -->
{% if not is_full_page_list %}
  {% set bottom_ads = get_active_ads('bottom') %}
  {% if bottom_ads %}
    <div class="ad-container bottom-banner">
      {% for ad in bottom_ads %}
        <a href="{{ ad.target_url }}" target="_blank" rel="noopener noreferrer">
          <img src="{{ ad.image_url }}" alt="{{ ad.title }}">
        </a>
      {% endfor %}
    </div>
  {% endif %}
{% endif %}

<nav class="bottom-nav">
  <!-- Bottom navigation remains the same -->
</nav>
</body>
</html>
"""

detail_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<!-- Previous head content remains the same -->
<style>
  /* Add ad styles for detail page */
  .ad-container.detail-page {
    margin: 25px auto;
    max-width: 1000px;
    text-align: center;
  }
</style>
</head>
<body>
<header>
  <a href="{{ url_for('home') }}" class="back-button"><i class="fas fa-arrow-left"></i>Back</a>
  <h1>MovieZone</h1>
</header>

<!-- Middle Banner Ad for Detail Page -->
{% set middle_ads = get_active_ads('middle') %}
{% if middle_ads %}
  <div class="ad-container detail-page">
    {% for ad in middle_ads %}
      <a href="{{ ad.target_url }}" target="_blank" rel="noopener noreferrer">
        <img src="{{ ad.image_url }}" alt="{{ ad.title }}" style="max-height: 150px;">
      </a>
    {% endfor %}
  </div>
{% endif %}

<main>
  <!-- Previous detail content remains the same -->
</main>

<nav class="bottom-nav">
  <!-- Bottom navigation remains the same -->
</nav>
</body>
</html>
"""

admin_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Admin Panel - MovieZone</title>
  <style>
    /* Previous styles remain the same */
    
    /* Tab styles for admin panel */
    .tab-container {
      display: flex;
      margin-bottom: 20px;
      border-bottom: 1px solid #333;
    }
    
    .tab {
      padding: 10px 20px;
      cursor: pointer;
      background: #282828;
      margin-right: 5px;
      border-radius: 5px 5px 0 0;
    }
    
    .tab.active {
      background: #1db954;
      color: #000;
      font-weight: bold;
    }
    
    .tab-content {
      display: none;
    }
    
    .tab-content.active {
      display: block;
    }
    
    .ad-image-preview {
      max-width: 200px;
      max-height: 100px;
      margin-top: 10px;
      display: none;
    }
  </style>
</head>
<body>
  <div class="tab-container">
    <div class="tab active" onclick="switchTab('content')">Content Management</div>
    <div class="tab" onclick="switchTab('ads')">Advertisement</div>
  </div>

  <!-- Content Management Tab -->
  <div id="content-tab" class="tab-content active">
    <!-- Previous content management form and list -->
  </div>

  <!-- Advertisement Management Tab -->
  <div id="ads-tab" class="tab-content">
    <h2>Add New Advertisement</h2>
    <form method="post" action="/add_ad">
      <div class="form-group">
        <label for="ad_title">Ad Title:</label>
        <input type="text" name="title" id="ad_title" required />
      </div>
      
      <div class="form-group">
        <label for="ad_image_url">Image URL:</label>
        <input type="url" name="image_url" id="ad_image_url" required 
               onchange="document.getElementById('ad-image-preview').src = this.value; 
                         document.getElementById('ad-image-preview').style.display = 'block';" />
        <img id="ad-image-preview" class="ad-image-preview" />
      </div>
      
      <div class="form-group">
        <label for="ad_target_url">Target URL:</label>
        <input type="url" name="target_url" id="ad_target_url" required />
      </div>
      
      <div class="form-group">
        <label for="ad_position">Position:</label>
        <select name="position" id="ad_position" required>
          <option value="top">Top Banner</option>
          <option value="middle">Middle Banner</option>
          <option value="bottom">Bottom Banner</option>
          <option value="sidebar">Sidebar</option>
        </select>
      </div>
      
      <div class="form-group">
        <label for="ad_start_date">Start Date:</label>
        <input type="date" name="start_date" id="ad_start_date" required />
      </div>
      
      <div class="form-group">
        <label for="ad_end_date">End Date:</label>
        <input type="date" name="end_date" id="ad_end_date" required />
      </div>
      
      <div class="form-group">
        <input type="checkbox" name="is_active" id="ad_is_active" value="true" checked>
        <label for="ad_is_active" style="display: inline-block;">Is Active?</label>
      </div>
      
      <button type="submit">Add Advertisement</button>
    </form>

    <h2 style="margin-top: 40px;">Manage Ads</h2>
    <div class="movie-list-container">
      {% if ads %}
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Position</th>
            <th>Active</th>
            <th>Dates</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {% for ad in ads %}
          <tr>
            <td>{{ ad.title }}</td>
            <td>{{ ad.position }}</td>
            <td>{% if ad.is_active %}Yes{% else %}No{% endif %}</td>
            <td>{{ ad.start_date }} to {{ ad.end_date }}</td>
            <td class="action-buttons">
              <a href="/edit_ad/{{ ad._id }}" class="edit-btn">Edit</a>
              <button class="delete-btn" onclick="confirmAdDelete('{{ ad._id }}', '{{ ad.title }}')">Delete</button>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% else %}
      <p style="text-align:center; color:#999;">No ads found.</p>
      {% endif %}
    </div>
  </div>

  <script>
    function switchTab(tabName) {
      // Hide all tab contents
      document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
      });
      
      // Deactivate all tabs
      document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
      });
      
      // Activate selected tab
      document.getElementById(tabName + '-tab').classList.add('active');
      event.currentTarget.classList.add('active');
    }
    
    function confirmAdDelete(adId, adTitle) {
      if (confirm('Are you sure you want to delete "' + adTitle + '" ad?')) {
        window.location.href = '/delete_ad/' + adId;
      }
    }
    
    // Previous JavaScript functions remain the same
  </script>
</body>
</html>
"""

edit_ad_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Edit Ad - MovieZone</title>
  <style>
    /* Same styles as admin panel */
  </style>
</head>
<body>
  <a href="{{ url_for('admin') }}" class="back-to-admin">&larr; Back to Admin Panel</a>
  <h2>Edit Advertisement: {{ ad.title }}</h2>
  <form method="post" action="/update_ad/{{ ad._id }}">
    <div class="form-group">
      <label for="ad_title">Ad Title:</label>
      <input type="text" name="title" id="ad_title" value="{{ ad.title }}" required />
    </div>
    
    <div class="form-group">
      <label for="ad_image_url">Image URL:</label>
      <input type="url" name="image_url" id="ad_image_url" value="{{ ad.image_url }}" required 
             onchange="document.getElementById('ad-image-preview').src = this.value;" />
      <img id="ad-image-preview" class="ad-image-preview" src="{{ ad.image_url }}" style="display: block;" />
    </div>
    
    <div class="form-group">
      <label for="ad_target_url">Target URL:</label>
      <input type="url" name="target_url" id="ad_target_url" value="{{ ad.target_url }}" required />
    </div>
    
    <div class="form-group">
      <label for="ad_position">Position:</label>
      <select name="position" id="ad_position" required>
        <option value="top" {% if ad.position == 'top' %}selected{% endif %}>Top Banner</option>
        <option value="middle" {% if ad.position == 'middle' %}selected{% endif %}>Middle Banner</option>
        <option value="bottom" {% if ad.position == 'bottom' %}selected{% endif %}>Bottom Banner</option>
        <option value="sidebar" {% if ad.position == 'sidebar' %}selected{% endif %}>Sidebar</option>
      </select>
    </div>
    
    <div class="form-group">
      <label for="ad_start_date">Start Date:</label>
      <input type="date" name="start_date" id="ad_start_date" value="{{ ad.start_date }}" required />
    </div>
    
    <div class="form-group">
      <label for="ad_end_date">End Date:</label>
      <input type="date" name="end_date" id="ad_end_date" value="{{ ad.end_date }}" required />
    </div>
    
    <div class="form-group">
      <input type="checkbox" name="is_active" id="ad_is_active" value="true" {% if ad.is_active %}checked{% endif %}>
      <label for="ad_is_active" style="display: inline-block;">Is Active?</label>
    </div>
    
    <button type="submit">Update Advertisement</button>
  </form>
</body>
</html>
"""
# --- END OF TEMPLATES ---

# --- ROUTES ---
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
    else:
        trending_movies_result = movies.find({"quality": "TRENDING"}).sort('_id', -1).limit(6)
        trending_movies_list = list(trending_movies_result)

        latest_movies_result = movies.find({
            "type": "movie",
            "quality": {"$ne": "TRENDING"},
            "is_coming_soon": {"$ne": True}
        }).sort('_id', -1).limit(6)
        latest_movies_list = list(latest_movies_result)

        latest_series_result = movies.find({
            "type": "series",
            "quality": {"$ne": "TRENDING"},
            "is_coming_soon": {"$ne": True}
        }).sort('_id', -1).limit(6)
        latest_series_list = list(latest_series_result)

        coming_soon_result = movies.find({"is_coming_soon": True}).sort('_id', -1).limit(6)
        coming_soon_movies_list = list(coming_soon_result)

    for m in movies_list + trending_movies_list + latest_movies_list + latest_series_list + coming_soon_movies_list:
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
            
            if TMDB_API_KEY and (not movie.get("tmdb_id") or movie.get("overview") == "No overview available." or not movie.get("poster")) and movie.get("type") == "movie":
                tmdb_id = movie.get("tmdb_id") 
                
                if not tmdb_id:
                    tmdb_search_type = "movie" if movie.get("type") == "movie" else "tv"
                    search_url = f"https://api.themoviedb.org/3/search/{tmdb_search_type}?api_key={TMDB_API_KEY}&query={movie['title']}"
                    try:
                        search_res = requests.get(search_url, timeout=5).json()
                        if search_res and "results" in search_res and search_res["results"]:
                            tmdb_id = search_res["results"][0].get("id")
                            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": {"tmdb_id": tmdb_id}})
                    except Exception as e:
                        print(f"Error during TMDb search: {e}")

                if tmdb_id:
                    tmdb_detail_type = "movie"
                    tmdb_detail_url = f"https://api.themoviedb.org/3/{tmdb_detail_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
                    try:
                        res = requests.get(tmdb_detail_url, timeout=5).json()
                        if res:
                            if movie.get("overview") == "No overview available." and res.get("overview"):
                                movie["overview"] = res.get("overview")
                            if not movie.get("poster") and res.get("poster_path"):
                                movie["poster"] = f"https://image.tmdb.org/t/p/w500{res['poster_path']}"
                            
                            release_date = res.get("release_date")
                            if movie.get("year") == "N/A" and release_date:
                                movie["year"] = release_date[:4]
                                movie["release_date"] = release_date
                            
                            if movie.get("vote_average") is None and res.get("vote_average"):
                                movie["vote_average"] = res.get("vote_average")
                            if movie.get("original_language") == "N/A" and res.get("original_language"):
                                movie["original_language"] = res.get("original_language")
                            
                            genres_names = []
                            for genre_obj in res.get("genres", []):
                                if genre_obj.get("id") in TMDb_Genre_Map:
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
                    except Exception as e:
                        print(f"Error fetching TMDb details: {e}")

        return render_template_string(detail_html, movie=movie, get_active_ads=get_active_ads)
    except Exception as e:
        print(f"Error in movie_detail: {e}")
        return render_template_string(detail_html, movie=None)

@app.route('/admin', methods=["GET", "POST"])
@requires_auth
def admin():
    if request.method == "POST":
        # Existing content management code remains the same
        pass

    admin_query = request.args.get('q')
    
    if admin_query:
        all_content = list(movies.find({"title": {"$regex": admin_query, "$options": "i"}}).sort('_id', -1))
    else:
        all_content = list(movies.find().sort('_id', -1))
    
    all_ads = list(ads.find().sort("created_at", -1))
    
    for content in all_content:
        content['_id'] = str(content['_id']) 
    
    for ad in all_ads:
        ad['_id'] = str(ad['_id'])

    return render_template_string(admin_html, movies=all_content, ads=all_ads, admin_query=admin_query)

@app.route('/add_ad', methods=["POST"])
@requires_auth
def add_ad():
    if request.method == "POST":
        ad_data = {
            "title": request.form.get("title"),
            "image_url": request.form.get("image_url"),
            "target_url": request.form.get("target_url"),
            "position": request.form.get("position"),
            "is_active": request.form.get("is_active") == "true",
            "start_date": request.form.get("start_date"),
            "end_date": request.form.get("end_date"),
            "created_at": datetime.datetime.utcnow()
        }
        
        try:
            ads.insert_one(ad_data)
            return redirect(url_for('admin'))
        except Exception as e:
            print(f"Error adding ad: {e}")
            return redirect(url_for('admin'))

@app.route('/edit_ad/<ad_id>', methods=["GET"])
@requires_auth
def edit_ad(ad_id):
    try:
        ad = ads.find_one({"_id": ObjectId(ad_id)})
        if not ad:
            return "Ad not found!", 404
        
        ad['_id'] = str(ad['_id'])
        return render_template_string(edit_ad_html, ad=ad)
    except Exception as e:
        print(f"Error editing ad: {e}")
        return redirect(url_for('admin'))

@app.route('/update_ad/<ad_id>', methods=["POST"])
@requires_auth
def update_ad(ad_id):
    try:
        updated_data = {
            "title": request.form.get("title"),
            "image_url": request.form.get("image_url"),
            "target_url": request.form.get("target_url"),
            "position": request.form.get("position"),
            "is_active": request.form.get("is_active") == "true",
            "start_date": request.form.get("start_date"),
            "end_date": request.form.get("end_date")
        }
        
        ads.update_one({"_id": ObjectId(ad_id)}, {"$set": updated_data})
        return redirect(url_for('admin'))
    except Exception as e:
        print(f"Error updating ad: {e}")
        return redirect(url_for('admin'))

@app.route('/delete_ad/<ad_id>')
@requires_auth
def delete_ad(ad_id):
    try:
        ads.delete_one({"_id": ObjectId(ad_id)})
    except Exception as e:
        print(f"Error deleting ad: {e}")
    
    return redirect(url_for('admin'))

# Existing category routes remain the same
@app.route('/trending_movies')
def trending_movies():
    trending_list = list(movies.find({"quality": "TRENDING"}).sort('_id', -1))
    for m in trending_list:
        m['_id'] = str(m['_id'])
    return render_template_string(index_html, movies=trending_list, query="Trending on MovieZone", is_full_page_list=True, get_active_ads=get_active_ads)

@app.route('/movies_only')
def movies_only():
    movie_list = list(movies.find({"type": "movie", "quality": {"$ne": "TRENDING"}, "is_coming_soon": {"$ne": True}}).sort('_id', -1))
    for m in movie_list:
        m['_id'] = str(m['_id'])
    return render_template_string(index_html, movies=movie_list, query="All Movies on MovieZone", is_full_page_list=True, get_active_ads=get_active_ads)

@app.route('/webseries')
def webseries():
    series_list = list(movies.find({"type": "series", "quality": {"$ne": "TRENDING"}, "is_coming_soon": {"$ne": True}}).sort('_id', -1))
    for m in series_list:
        m['_id'] = str(m['_id'])
    return render_template_string(index_html, movies=series_list, query="All Web Series on MovieZone", is_full_page_list=True, get_active_ads=get_active_ads)

@app.route('/coming_soon')
def coming_soon():
    coming_soon_list = list(movies.find({"is_coming_soon": True}).sort('_id', -1))
    for m in coming_soon_list:
        m['_id'] = str(m['_id'])
    return render_template_string(index_html, movies=coming_soon_list, query="Coming Soon to MovieZone", is_full_page_list=True, get_active_ads=get_active_ads)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
