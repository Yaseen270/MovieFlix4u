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
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")

# --- অ্যাডমিন অথেন্টিকেশন ফাংশন ---
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
# --- অথেন্টিকেশন শেষ ---

# Check if environment variables are set
if not MONGO_URI:
    print("Error: MONGO_URI environment variable must be set. Exiting.")
    exit(1)
if not TMDB_API_KEY:
    print("Warning: TMDB_API_KEY is not set. Movie details will not be auto-fetched.")

# Database connection
try:
    client = MongoClient(MONGO_URI)
    db = client["movie_db"]
    movies = db["movies"]
    settings = db["settings"]
    feedback = db["feedback"]
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}. Exiting.")
    exit(1)


# === Context Processor: সমস্ত টেমপ্লেটে বিজ্ঞাপনের কোড সহজলভ্য করার জন্য ===
@app.context_processor
def inject_ads():
    ad_codes = settings.find_one()
    return dict(ad_settings=(ad_codes or {}))


# --- START OF index_html TEMPLATE ---
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
<title>MovieFlix9u - Your Entertainment Hub</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;500;700&display=swap');
  :root {
      --netflix-red: #E50914; --netflix-black: #141414;
      --text-light: #f5f5f5; --text-dark: #a0a0a0;
      --nav-height: 60px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Roboto', sans-serif; background-color: var(--netflix-black);
    color: var(--text-light); overflow-x: hidden;
  }
  a { text-decoration: none; color: inherit; }
  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: #222; }
  ::-webkit-scrollbar-thumb { background: #555; }
  ::-webkit-scrollbar-thumb:hover { background: var(--netflix-red); }

  .main-nav {
      position: fixed; top: 0; left: 0; width: 100%; padding: 15px 50px;
      display: flex; justify-content: space-between; align-items: center; z-index: 100;
      transition: background-color 0.3s ease;
      background: linear-gradient(to bottom, rgba(0,0,0,0.8) 10%, rgba(0,0,0,0));
  }
  .main-nav.scrolled { background-color: var(--netflix-black); }
  .logo {
      font-family: 'Bebas Neue', sans-serif; font-size: 32px; color: var(--netflix-red);
      font-weight: 700; letter-spacing: 1px;
  }
  .search-input {
      background-color: rgba(0,0,0,0.7); border: 1px solid #777;
      color: var(--text-light); padding: 8px 15px; border-radius: 4px;
      transition: width 0.3s ease, background-color 0.3s ease; width: 250px;
  }
  .search-input:focus { background-color: rgba(0,0,0,0.9); border-color: var(--text-light); outline: none; }

  .tags-section {
    padding: 80px 50px 20px 50px;
    background-color: var(--netflix-black);
  }
  .tags-container {
    display: flex; flex-wrap: wrap;
    justify-content: center;
    gap: 10px;
  }
  .tag-link {
    padding: 6px 16px;
    background-color: rgba(255, 255, 255, 0.1);
    border: 1px solid #444; border-radius: 50px;
    font-weight: 500; font-size: 0.85rem;
    transition: background-color 0.3s, border-color 0.3s, color 0.3s;
  }
  .tag-link:hover { background-color: var(--netflix-red); border-color: var(--netflix-red); color: white; }

  .hero-section { height: 85vh; position: relative; color: white; overflow: hidden; }
  .hero-slide {
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      background-size: cover; background-position: center top;
      display: flex; align-items: flex-end; padding: 50px;
      opacity: 0; transition: opacity 1.5s ease-in-out; z-index: 1;
  }
  .hero-slide.active { opacity: 1; z-index: 2; }
  .hero-slide::before {
      content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(to top, var(--netflix-black) 10%, transparent 50%),
                  linear-gradient(to right, rgba(0,0,0,0.8) 0%, transparent 60%);
  }
  .hero-content { position: relative; z-index: 3; max-width: 50%; }
  .hero-title { font-family: 'Bebas Neue', sans-serif; font-size: 5rem; font-weight: 700; margin-bottom: 1rem; line-height: 1; }
  .hero-overview {
      font-size: 1.1rem; line-height: 1.5; margin-bottom: 1.5rem; max-width: 600px;
      display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  }
  .hero-buttons .btn {
      padding: 8px 20px; /* MODIFIED: Made smaller */
      margin-right: 0.8rem; /* MODIFIED: Adjusted margin */
      border: none; border-radius: 4px;
      font-size: 0.9rem; /* MODIFIED: Made smaller */
      font-weight: 700; cursor: pointer; transition: opacity 0.3s ease;
      display: inline-flex; align-items: center; gap: 8px;
  }
  .btn.btn-primary { background-color: var(--netflix-red); color: white; }
  .btn.btn-secondary { background-color: rgba(109, 109, 110, 0.7); color: white; }
  .btn:hover { opacity: 0.8; }

  main { padding-top: 0; }
  .carousel-row { margin: 40px 0; position: relative; }
  .carousel-header {
      display: flex; justify-content: space-between; align-items: center;
      margin: 0 50px 15px 50px;
  }
  .carousel-title { font-family: 'Roboto', sans-serif; font-weight: 700; font-size: 1.6rem; margin: 0; }
  .see-all-link { color: var(--text-dark); font-weight: 700; font-size: 0.9rem; }
  .carousel-wrapper { position: relative; }
  .carousel-content {
      display: flex; gap: 10px; padding: 0 50px; overflow-x: scroll;
      scrollbar-width: none; -ms-overflow-style: none; scroll-behavior: smooth;
  }
  .carousel-content::-webkit-scrollbar { display: none; }
  .carousel-arrow {
      position: absolute; top: 0; height: 100%; transform: translateY(0);
      background-color: rgba(20, 20, 20, 0.5); border: none; color: white;
      font-size: 2.5rem; cursor: pointer; z-index: 10; width: 50px;
      display: flex; align-items: center; justify-content: center;
      opacity: 0; transition: opacity 0.3s ease;
  }
  .carousel-row:hover .carousel-arrow { opacity: 1; }
  .carousel-arrow.prev { left: 0; }
  .carousel-arrow.next { right: 0; }

  .movie-card {
      flex: 0 0 16.66%; min-width: 220px; border-radius: 4px; overflow: hidden;
      cursor: pointer; transition: transform 0.3s ease, box-shadow 0.3s ease;
      position: relative; background-color: #222; display: block;
  }
  .movie-poster { width: 100%; aspect-ratio: 2 / 3; object-fit: cover; display: block; }
  .poster-badge {
    position: absolute; top: 10px; left: 10px; background-color: var(--netflix-red);
    color: white; padding: 5px 10px; font-size: 12px; font-weight: 700;
    border-radius: 4px; z-index: 3; box-shadow: 0 2px 5px rgba(0,0,0,0.5);
  }
  .card-info-overlay {
      position: absolute; bottom: 0; left: 0; right: 0; padding: 20px 10px 10px 10px;
      background: linear-gradient(to top, rgba(0,0,0,0.95) 20%, transparent 100%);
      color: white; text-align: center; opacity: 0;
      transform: translateY(20px); transition: opacity 0.3s ease, transform 0.3s ease; z-index: 2;
  }
  .card-info-title { font-size: 1rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  @keyframes rgb-glow {
    0% { box-shadow: 0 0 12px #e50914, 0 0 4px #e50914; }
    33% { box-shadow: 0 0 12px #4158D0, 0 0 4px #4158D0; }
    66% { box-shadow: 0 0 12px #C850C0, 0 0 4px #C850C0; }
    100% { box-shadow: 0 0 12px #e50914, 0 0 4px #e50914; }
  }
  @media (hover: hover) {
    .movie-card:hover { 
        transform: scale(1.05); z-index: 5;
        animation: rgb-glow 2.5s infinite linear;
    }
    .movie-card:hover .card-info-overlay { opacity: 1; transform: translateY(0); }
  }

  .full-page-grid-container { padding: 100px 50px 50px 50px; }
  .full-page-grid-title { font-size: 2.5rem; font-weight: 700; margin-bottom: 30px; }
  .full-page-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px;
  }
  .full-page-grid .movie-card { min-width: 0; }
  
  .bottom-nav {
      display: none; position: fixed; bottom: 0; left: 0; right: 0;
      height: var(--nav-height); background-color: #181818;
      border-top: 1px solid #282828; justify-content: space-around;
      align-items: center; z-index: 200;
  }
  .nav-item {
      display: flex; flex-direction: column; align-items: center;
      color: var(--text-dark); font-size: 10px; flex-grow: 1;
      padding: 5px 0; transition: color 0.2s ease;
  }
  .nav-item i { font-size: 20px; margin-bottom: 4px; }
  .nav-item.active { color: var(--text-light); }
  .nav-item.active .fa-home, .nav-item.active .fa-envelope, .nav-item.active .fa-layer-group { color: var(--netflix-red); }
  .ad-container { margin: 40px 50px; display: flex; justify-content: center; align-items: center; }

  .telegram-join-section {
    background-color: #181818; padding: 40px 20px;
    margin-top: 50px; text-align: center;
  }
  .telegram-join-section .telegram-icon {
    font-size: 4rem; color: #2AABEE; margin-bottom: 15px;
  }
  .telegram-join-section h2 {
    font-family: 'Bebas Neue', sans-serif; font-size: 2.5rem;
    color: var(--text-light); margin-bottom: 10px;
  }
  .telegram-join-section p {
    font-size: 1.1rem; color: var(--text-dark); max-width: 600px;
    margin: 0 auto 25px auto;
  }
  .telegram-join-button {
    display: inline-flex; align-items: center; gap: 10px;
    background-color: #2AABEE; color: white;
    padding: 12px 30px; border-radius: 50px;
    font-size: 1.1rem; font-weight: 700;
    transition: transform 0.2s ease, background-color 0.2s ease;
  }
  .telegram-join-button:hover { transform: scale(1.05); background-color: #1e96d1; }
  .telegram-join-button i { font-size: 1.3rem; }

  @media (max-width: 768px) {
      body { padding-bottom: var(--nav-height); }
      .main-nav { padding: 10px 15px; }
      .logo { font-size: 24px; }
      .search-input { width: 150px; }
      .tags-section { padding: 80px 15px 15px 15px; }
      .tag-link { padding: 6px 15px; font-size: 0.8rem; }
      .hero-section { height: 60vh; }
      .hero-slide { padding: 15px; align-items: center; }
      .hero-content { max-width: 90%; text-align: center; }
      .hero-title { font-size: 2.8rem; }
      .hero-overview { display: none; }
      .carousel-row { margin: 25px 0; }
      .carousel-header { margin: 0 15px 10px 15px; }
      .carousel-title { font-size: 1.2rem; }
      .carousel-content { padding: 0 15px; gap: 8px; }
      .movie-card { min-width: 130px; }
      .full-page-grid-container { padding: 80px 15px 30px; }
      .full-page-grid-title { font-size: 1.8rem; }
      .full-page-grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; }
      .bottom-nav { display: flex; }
      .ad-container { margin: 25px 15px; }
      .telegram-join-section h2 { font-size: 2rem; }
      .telegram-join-section p { font-size: 1rem; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css">
</head>
<body>
<header class="main-nav">
  <a href="{{ url_for('home') }}" class="logo">MovieFlix9u</a>
  <form method="GET" action="/" class="search-form">
    <input type="search" name="q" class="search-input" placeholder="Search..." value="{{ query|default('') }}" />
  </form>
</header>

<main>
  {% macro render_movie_card(m) %}
    <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
      {% if m.poster_badge %}<div class="poster-badge">{{ m.poster_badge }}</div>{% endif %}
      <img class="movie-poster" loading="lazy" src="{{ m.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ m.title }}">
      <div class="card-info-overlay"><h4 class="card-info-title">{{ m.title }}</h4></div>
    </a>
  {% endmacro %}

  {% if is_full_page_list %}
    <div class="full-page-grid-container">
      <h2 class="full-page-grid-title">{{ query }}</h2>
      {% if movies|length == 0 %}<p style="text-align:center; color: var(--text-dark); margin-top: 40px;">No content found.</p>
      {% else %}<div class="full-page-grid">{% for m in movies %}{{ render_movie_card(m) }}{% endfor %}</div>{% endif %}
    </div>
  {% else %}
    {% if all_badges %}
    <div class="tags-section">
        <div class="tags-container">
            {% for badge in all_badges %}<a href="{{ url_for('movies_by_badge', badge_name=badge) }}" class="tag-link">{{ badge }}</a>{% endfor %}
        </div>
    </div>
    {% endif %}
    {% if recently_added %}
      <div class="hero-section">
        {% for movie in recently_added %}
          <div class="hero-slide {% if loop.first %}active{% endif %}" style="background-image: url('{{ movie.poster or '' }}');">
            <div class="hero-content">
              <h1 class="hero-title">{{ movie.title }}</h1>
              <p class="hero-overview">{{ movie.overview }}</p>
              <div class="hero-buttons">
                 {% if movie.watch_link and not movie.is_coming_soon %}<a href="{{ url_for('watch_movie', movie_id=movie._id) }}" class="btn btn-primary"><i class="fas fa-play"></i> Watch Now</a>{% endif %}
                <a href="{{ url_for('movie_detail', movie_id=movie._id) }}" class="btn btn-secondary"><i class="fas fa-info-circle"></i> More Info</a>
              </div>
            </div>
          </div>
        {% endfor %}
      </div>
    {% endif %}

    {% macro render_carousel(title, movies_list, endpoint) %}
      {% if movies_list %}
      <div class="carousel-row">
        <div class="carousel-header">
          <h2 class="carousel-title">{{ title }}</h2>
          <a href="{{ url_for(endpoint) }}" class="see-all-link">See All ></a>
        </div>
        <div class="carousel-wrapper">
          <div class="carousel-content">{% for m in movies_list %}{{ render_movie_card(m) }}{% endfor %}</div>
          <button class="carousel-arrow prev"><i class="fas fa-chevron-left"></i></button>
          <button class="carousel-arrow next"><i class="fas fa-chevron-right"></i></button>
        </div>
      </div>
      {% endif %}
    {% endmacro %}
    
    {{ render_carousel('Trending Now', trending_movies, 'trending_movies') }}
    {% if ad_settings.banner_ad_code %}<div class="ad-container">{{ ad_settings.banner_ad_code|safe }}</div>{% endif %}
    {{ render_carousel('Latest Movies', latest_movies, 'movies_only') }}
    {% if ad_settings.native_banner_code %}<div class="ad-container">{{ ad_settings.native_banner_code|safe }}</div>{% endif %}
    {{ render_carousel('Web Series', latest_series, 'webseries') }}
    {{ render_carousel('Recently Added', recently_added_full, 'recently_added_all') }}
    {{ render_carousel('Coming Soon', coming_soon_movies, 'coming_soon') }}
    
    <div class="telegram-join-section">
        <i class="fa-brands fa-telegram telegram-icon"></i>
        <h2>Join Our Telegram Channel</h2>
        <p>Get the latest movie updates, news, and direct download links right on your phone!</p>
        <a href="https://t.me/MovieFlix9u" target="_blank" class="telegram-join-button">
            <i class="fa-brands fa-telegram"></i> Join Main Channel
        </a>
    </div>
  {% endif %}
</main>

<nav class="bottom-nav">
  <a href="{{ url_for('home') }}" class="nav-item {% if request.endpoint == 'home' %}active{% endif %}"><i class="fas fa-home"></i><span>Home</span></a>
  <a href="{{ url_for('genres_page') }}" class="nav-item {% if request.endpoint == 'genres_page' %}active{% endif %}"><i class="fas fa-layer-group"></i><span>Genres</span></a>
  <a href="{{ url_for('movies_only') }}" class="nav-item {% if request.endpoint == 'movies_only' %}active{% endif %}"><i class="fas fa-film"></i><span>Movies</span></a>
  <a href="{{ url_for('webseries') }}" class="nav-item {% if request.endpoint == 'webseries' %}active{% endif %}"><i class="fas fa-tv"></i><span>Series</span></a>
  <a href="{{ url_for('contact') }}" class="nav-item {% if request.endpoint == 'contact' %}active{% endif %}"><i class="fas fa-envelope"></i><span>Request</span></a>
</nav>

<script>
    const nav = document.querySelector('.main-nav');
    window.addEventListener('scroll', () => { window.scrollY > 50 ? nav.classList.add('scrolled') : nav.classList.remove('scrolled'); });
    document.querySelectorAll('.carousel-arrow').forEach(button => {
        button.addEventListener('click', () => {
            const carousel = button.closest('.carousel-wrapper').querySelector('.carousel-content');
            const scroll = carousel.clientWidth * 0.8;
            carousel.scrollLeft += button.classList.contains('next') ? scroll : -scroll;
        });
    });
    document.addEventListener('DOMContentLoaded', function() {
        const slides = document.querySelectorAll('.hero-slide');
        if (slides.length > 1) {
            let currentSlide = 0;
            const showSlide = (index) => slides.forEach((s, i) => s.classList.toggle('active', i === index));
            setInterval(() => { currentSlide = (currentSlide + 1) % slides.length; showSlide(currentSlide); }, 5000);
        }
    });
</script>
{% if ad_settings.popunder_code %}{{ ad_settings.popunder_code|safe }}{% endif %}
{% if ad_settings.social_bar_code %}{{ ad_settings.social_bar_code|safe }}{% endif %}
</body>
</html>
"""
# --- END OF index_html TEMPLATE ---


# --- START OF genres_html TEMPLATE ---
genres_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
<title>{{ title }} - MovieFlix9u</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;500;700&display=swap');
  :root { --netflix-red: #E50914; --netflix-black: #141414; --text-light: #f5f5f5; --text-dark: #a0a0a0; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Roboto', sans-serif; background-color: var(--netflix-black); color: var(--text-light); }
  a { text-decoration: none; color: inherit; }
  
  .main-container { padding: 100px 50px 50px; }
  .page-title { font-family: 'Bebas Neue', sans-serif; font-size: 3rem; color: var(--netflix-red); margin-bottom: 30px; }
  .back-button { color: var(--text-light); font-size: 1rem; margin-bottom: 20px; display: inline-block; }
  .back-button:hover { color: var(--netflix-red); }
  
  .genre-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 20px;
  }
  .genre-card {
    background: linear-gradient(45deg, #2c2c2c, #1a1a1a);
    border-radius: 8px;
    padding: 30px 20px;
    text-align: center;
    font-size: 1.4rem;
    font-weight: 700;
    transition: transform 0.3s ease, background 0.3s ease;
    border: 1px solid #444;
  }
  .genre-card:hover {
    transform: translateY(-5px) scale(1.03);
    background: linear-gradient(45deg, var(--netflix-red), #b00710);
    border-color: var(--netflix-red);
  }
  @media (max-width: 768px) {
    .main-container { padding: 80px 15px 30px; }
    .page-title { font-size: 2.2rem; }
    .genre-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; }
    .genre-card { font-size: 1.1rem; padding: 25px 15px; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css">
</head>
<body>
  <div class="main-container">
    <a href="{{ url_for('home') }}" class="back-button"><i class="fas fa-arrow-left"></i> Back to Home</a>
    <h1 class="page-title">{{ title }}</h1>
    <div class="genre-grid">
      {% for genre in genres %}
        <a href="{{ url_for('movies_by_genre', genre_name=genre) }}" class="genre-card">
          <span>{{ genre }}</span>
        </a>
      {% endfor %}
    </div>
  </div>
  {% if ad_settings.popunder_code %}{{ ad_settings.popunder_code|safe }}{% endif %}
  {% if ad_settings.social_bar_code %}{{ ad_settings.social_bar_code|safe }}{% endif %}
</body>
</html>
"""
# --- END OF genres_html TEMPLATE ---


# --- START OF detail_html TEMPLATE ---
detail_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
<title>{{ movie.title if movie else "Content Not Found" }} - MovieFlix9u</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;500;700&display=swap');
  :root { --netflix-red: #E50914; --netflix-black: #141414; --text-light: #f5f5f5; --text-dark: #a0a0a0; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Roboto', sans-serif; background: var(--netflix-black); color: var(--text-light); }
  .detail-header { position: absolute; top: 0; left: 0; right: 0; padding: 20px 50px; z-index: 100; }
  .back-button { color: var(--text-light); font-size: 1.2rem; font-weight: 700; text-decoration: none; display: flex; align-items: center; gap: 10px; transition: color 0.3s ease; }
  .back-button:hover { color: var(--netflix-red); }
  .detail-hero { position: relative; width: 100%; display: flex; align-items: center; justify-content: center; padding: 100px 0; }
  .detail-hero-background { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background-size: cover; background-position: center; filter: blur(20px) brightness(0.4); transform: scale(1.1); }
  .detail-hero::after { content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(to top, rgba(20,20,20,1) 0%, rgba(20,20,20,0.6) 50%, rgba(20,20,20,1) 100%); }
  .detail-content-wrapper { position: relative; z-index: 2; display: flex; gap: 40px; max-width: 1200px; padding: 0 50px; width: 100%; }
  .detail-poster { width: 300px; height: 450px; flex-shrink: 0; border-radius: 8px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); object-fit: cover; }
  .detail-info { flex-grow: 1; max-width: 65%; }
  .detail-title { font-family: 'Bebas Neue', sans-serif; font-size: 4.5rem; font-weight: 700; line-height: 1.1; margin-bottom: 20px; }
  .detail-meta { display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 25px; font-size: 1rem; color: var(--text-dark); }
  .detail-meta span { font-weight: 700; color: var(--text-light); }
  .detail-overview { font-size: 1.1rem; line-height: 1.6; margin-bottom: 30px; }
  .watch-now-btn { background-color: var(--netflix-red); color: white; padding: 15px 30px; font-size: 1.2rem; font-weight: 700; border: none; border-radius: 5px; cursor: pointer; display: inline-flex; align-items: center; gap: 10px; text-decoration: none; margin-bottom: 25px; transition: transform 0.2s ease, background-color 0.2s ease; }
  .watch-now-btn:hover { transform: scale(1.05); background-color: #f61f29; }
  .section-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 20px; padding-bottom: 5px; border-bottom: 2px solid var(--netflix-red); display: inline-block; }
  .video-container { position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; background: #000; border-radius: 8px; }
  .video-container iframe { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
  .download-section { margin-top: 30px; }
  .download-button, .episode-download-button { display: inline-block; padding: 12px 25px; background-color: #444; color: white; text-decoration: none; border-radius: 4px; font-weight: 700; transition: background-color 0.3s ease; margin-right: 10px; margin-bottom: 10px; text-align: center; vertical-align: middle; }
  .copy-button { background-color: #555; color: white; border: none; padding: 8px 15px; font-size: 0.9rem; cursor: pointer; border-radius: 4px; margin-left: -5px; margin-bottom: 10px; vertical-align: middle; }
  .episode-item { margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #333; }
  .episode-title { font-size: 1.2rem; font-weight: 700; margin-bottom: 8px; color: #fff; }
  .ad-container { margin: 30px 0; text-align: center; }
  .related-section-container { padding: 40px 0; background-color: #181818; }
  .carousel-row { margin: 40px 0; position: relative; }
  .carousel-wrapper { position: relative; }
  .carousel-content { display: flex; gap: 10px; padding: 0 50px; overflow-x: scroll; scrollbar-width: none; scroll-behavior: smooth; }
  .carousel-content::-webkit-scrollbar { display: none; }
  .carousel-arrow { position: absolute; top: 0; height: 100%; background-color: rgba(20, 20, 20, 0.5); border: none; color: white; font-size: 2.5rem; cursor: pointer; z-index: 10; width: 50px; display: flex; align-items: center; justify-content: center; opacity: 0; transition: opacity 0.3s ease; }
  .carousel-row:hover .carousel-arrow { opacity: 1; }
  .carousel-arrow.prev { left: 0; }
  .carousel-arrow.next { right: 0; }
  .related-movie-card-wrapper { flex: 0 0 16.66%; min-width: 220px; }
  .movie-card { width: 100%; border-radius: 4px; overflow: hidden; cursor: pointer; transition: transform 0.3s ease; display: block; position: relative; }
  .movie-poster { width: 100%; aspect-ratio: 2 / 3; object-fit: cover; display: block; }
  .poster-badge { position: absolute; top: 10px; left: 10px; background-color: var(--netflix-red); color: white; padding: 5px 10px; font-size: 12px; font-weight: 700; border-radius: 4px; z-index: 3; }
  
  @keyframes rgb-glow {
    0% { box-shadow: 0 0 12px #e50914, 0 0 4px #e50914; } 33% { box-shadow: 0 0 12px #4158D0, 0 0 4px #4158D0; }
    66% { box-shadow: 0 0 12px #C850C0, 0 0 4px #C850C0; } 100% { box-shadow: 0 0 12px #e50914, 0 0 4px #e50914; }
  }
  @media (hover: hover) { .movie-card:hover { transform: scale(1.05); z-index: 5; animation: rgb-glow 2.5s infinite linear; } }
  
  @media (max-width: 992px) {
    .detail-content-wrapper { flex-direction: column; align-items: center; text-align: center; }
    .detail-info { max-width: 100%; } .detail-title { font-size: 3.5rem; }
  }
  @media (max-width: 768px) {
    .detail-header { padding: 20px; } .detail-hero { padding: 80px 20px 40px; }
    .detail-poster { width: 60%; max-width: 220px; height: auto; }
    .detail-title { font-size: 2.2rem; }
    .watch-now-btn, .download-button, .episode-download-button, .copy-button { display: block; width: 100%; max-width: 320px; margin: 0 auto 10px auto; }
    .section-title { margin-left: 15px !important; } .related-section-container { padding: 20px 0; }
    .carousel-content { padding: 0 15px; } .related-movie-card-wrapper { min-width: 130px; }
    .carousel-arrow { display: none; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css">
</head>
<body>
{% macro render_movie_card(m) %}
    <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
    {% if m.poster_badge %}<div class="poster-badge">{{ m.poster_badge }}</div>{% endif %}
    <img class="movie-poster" loading="lazy" src="{{ m.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ m.title }}">
    </a>
{% endmacro %}

<header class="detail-header"><a href="{{ url_for('home') }}" class="back-button"><i class="fas fa-arrow-left"></i> Back to Home</a></header>
{% if movie %}
<div class="detail-hero" style="min-height: auto; padding-bottom: 60px;">
  <div class="detail-hero-background" style="background-image: url('{{ movie.poster }}');"></div>
  <div class="detail-content-wrapper">
    <img class="detail-poster" src="{{ movie.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ movie.title }}">
    <div class="detail-info">
      <h1 class="detail-title">{{ movie.title }}</h1>
      <div class="detail-meta">
        {% if movie.release_date %}<span>{{ movie.release_date.split('-')[0] }}</span>{% endif %}
        {% if movie.vote_average %}<span><i class="fas fa-star" style="color:#f5c518;"></i> {{ "%.1f"|format(movie.vote_average) }}</span>{% endif %}
        {% if movie.genres %}<span>{{ movie.genres | join(' • ') }}</span>{% endif %}
      </div>
      <p class="detail-overview">{{ movie.overview }}</p>
      {% if movie.watch_link and movie.type == 'movie' and not movie.is_coming_soon %}<a href="{{ url_for('watch_movie', movie_id=movie._id) }}" class="watch-now-btn"><i class="fas fa-play"></i> Watch Now</a>{% endif %}
      {% if ad_settings.banner_ad_code %}<div class="ad-container">{{ ad_settings.banner_ad_code|safe }}</div>{% endif %}
      {% if trailer_key %}<div class="trailer-section"><h3 class="section-title">Watch Trailer</h3><div class="video-container"><iframe src="https://www.youtube.com/embed/{{ trailer_key }}" frameborder="0" allowfullscreen></iframe></div></div>{% endif %}
      {% if ad_settings.native_banner_code %}<div class="ad-container">{{ ad_settings.native_banner_code|safe }}</div>{% endif %}
      <div style="margin: 20px 0;"><a href="{{ url_for('contact', report_id=movie._id, title=movie.title) }}" class="download-button" style="background-color:#5a5a5a; text-align:center;"><i class="fas fa-flag"></i> Report a Problem</a></div>
      <div class="download-section">
        {% if movie.is_coming_soon %}<h3 class="section-title">Coming Soon</h3>
        {% elif movie.type == 'movie' and movie.links %}<h3 class="section-title">Download Links</h3>{% for link_item in movie.links %}<div><a class="download-button" href="{{ link_item.url }}" target="_blank" rel="noopener"><i class="fas fa-download"></i> {{ link_item.quality }} [{{ link_item.size or 'N/A' }}]</a><button class="copy-button" onclick="copyToClipboard('{{ link_item.url }}')"><i class="fas fa-copy"></i> Copy</button></div>{% endfor %}
        {% elif movie.type == 'series' and movie.episodes %}<h3 class="section-title">Episodes</h3>{% for episode in movie.episodes | sort(attribute='episode_number') %}<div class="episode-item"><h4 class="episode-title">E{{ episode.episode_number }}: {{ episode.title }}</h4>{% if episode.overview %}<p class="episode-overview-text">{{ episode.overview }}</p>{% endif %}{% if episode.watch_link %}<a href="{{ url_for('watch_movie', movie_id=movie._id, ep=episode.episode_number) }}" class="episode-download-button" style="background-color: var(--netflix-red);"><i class="fas fa-play"></i> Watch Episode</a>{% endif %}{% if episode.links %}{% for link_item in episode.links %}<div><a class="episode-download-button" href="{{ link_item.url }}" target="_blank" rel="noopener"><i class="fas fa-download"></i> {{ link_item.quality }}</a><button class="copy-button" onclick="copyToClipboard('{{ link_item.url }}')"><i class="fas fa-copy"></i></button></div>{% endfor %}{% endif %}</div>{% endfor %}
        {% endif %}
        {% if not movie.links and not movie.episodes and not movie.is_coming_soon %}<p class="no-link-message">No download links available.</p>{% endif %}
      </div>
    </div>
  </div>
</div>
{% if related_movies %}
<div class="related-section-container">
    <div class="carousel-row" style="margin-top: 20px; margin-bottom: 20px;">
        <h3 class="section-title" style="margin-left: 50px; border-color: var(--netflix-red); color: white;">You Might Also Like</h3>
        <div class="carousel-wrapper">
            <div class="carousel-content">{% for m in related_movies %}<div class="related-movie-card-wrapper">{{ render_movie_card(m) }}</div>{% endfor %}</div>
            <button class="carousel-arrow prev"><i class="fas fa-chevron-left"></i></button>
            <button class="carousel-arrow next"><i class="fas fa-chevron-right"></i></button>
        </div>
    </div>
</div>
{% endif %}
{% else %}<div style="display:flex; justify-content:center; align-items:center; height:100vh;"><h2>Content not found.</h2></div>{% endif %}
<script>
function copyToClipboard(text) { navigator.clipboard.writeText(text).then(() => alert('Link copied!'), () => alert('Copy failed!')); }
document.querySelectorAll('.carousel-arrow').forEach(button => {
    button.addEventListener('click', () => {
        const carousel = button.closest('.carousel-wrapper').querySelector('.carousel-content');
        const scrollAmount = carousel.clientWidth * 0.8;
        carousel.scrollLeft += button.classList.contains('next') ? scrollAmount : -scrollAmount;
    });
});
</script>
{% if ad_settings.popunder_code %}{{ ad_settings.popunder_code|safe }}{% endif %}
{% if ad_settings.social_bar_code %}{{ ad_settings.social_bar_code|safe }}{% endif %}
</body>
</html>
"""
# --- END OF detail_html TEMPLATE ---


# --- START OF watch_html TEMPLATE ---
watch_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Watching: {{ title }}</title>
<style> body, html { margin: 0; padding: 0; height: 100%; overflow: hidden; background-color: #000; } .player-container { width: 100%; height: 100%; } .player-container iframe { width: 100%; height: 100%; border: 0; } </style>
</head>
<body>
    <div class="player-container"><iframe src="{{ watch_link }}" allowfullscreen allowtransparency allow="autoplay" scrolling="no" frameborder="0"></iframe></div>
    {% if ad_settings.popunder_code %}{{ ad_settings.popunder_code|safe }}{% endif %}
    {% if ad_settings.social_bar_code %}{{ ad_settings.social_bar_code|safe }}{% endif %}
</body>
</html>
"""
# --- END OF watch_html TEMPLATE ---


# --- START OF admin_html TEMPLATE ---
admin_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Admin Panel - MovieFlix9u</title><meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { --netflix-red: #E50914; --netflix-black: #141414; --dark-gray: #222; --light-gray: #333; --text-light: #f5f5f5; }
    body { font-family: 'Roboto', sans-serif; background: var(--netflix-black); color: var(--text-light); padding: 20px; }
    h2, h3 { font-family: 'Bebas Neue', sans-serif; color: var(--netflix-red); }
    h2 { font-size: 2.5rem; margin-bottom: 20px; } h3 { font-size: 1.5rem; margin: 20px 0 10px 0;}
    form { max-width: 800px; margin: 0 auto 40px auto; background: var(--dark-gray); padding: 25px; border-radius: 8px;}
    .form-group { margin-bottom: 15px; } .form-group label { display: block; margin-bottom: 8px; font-weight: bold; }
    input[type="text"], input[type="url"], textarea, select, input[type="number"], input[type="email"] { width: 100%; padding: 12px; border-radius: 4px; border: 1px solid var(--light-gray); font-size: 1rem; background: var(--light-gray); color: var(--text-light); box-sizing: border-box; }
    input[type="checkbox"] { width: auto; margin-right: 10px; transform: scale(1.2); }
    textarea { resize: vertical; min-height: 100px; }
    button[type="submit"], .add-episode-btn { background: var(--netflix-red); color: white; font-weight: 700; cursor: pointer; border: none; padding: 12px 25px; border-radius: 4px; font-size: 1rem; transition: background 0.3s ease; }
    button[type="submit"]:hover, .add-episode-btn:hover { background: #b00710; }
    table { display: block; overflow-x: auto; white-space: nowrap; width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid var(--light-gray); }
    th { background: #252525; } td { background: var(--dark-gray); }
    .action-buttons { display: flex; gap: 10px; }
    .action-buttons a, .action-buttons button, .delete-btn { padding: 6px 12px; border-radius: 4px; text-decoration: none; color: white; border: none; cursor: pointer; transition: opacity 0.3s ease; }
    .edit-btn { background: #007bff; } .delete-btn { background: #dc3545; }
    .action-buttons a:hover, .action-buttons button:hover, .delete-btn:hover { opacity: 0.8; }
    .episode-item { border: 1px solid var(--light-gray); padding: 15px; margin-bottom: 15px; border-radius: 5px; }
    hr.section-divider { border: 0; height: 2px; background-color: var(--light-gray); margin: 40px 0; }
  </style>
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
  <h2>বিজ্ঞাপন পরিচালনা (Ad Management)</h2>
  <form action="{{ url_for('save_ads') }}" method="post">
    <div class="form-group"><label>Pop-Under / OnClick Ad Code</label><textarea name="popunder_code" rows="4">{{ ad_settings.popunder_code or '' }}</textarea></div>
    <div class="form-group"><label>Social Bar / Sticky Ad Code</label><textarea name="social_bar_code" rows="4">{{ ad_settings.social_bar_code or '' }}</textarea></div>
    <div class="form-group"><label>ব্যানার বিজ্ঞাপন কোড (Banner Ad)</label><textarea name="banner_ad_code" rows="4">{{ ad_settings.banner_ad_code or '' }}</textarea></div>
    <div class="form-group"><label>নেটিভ ব্যানার বিজ্ঞাপন (Native Banner)</label><textarea name="native_banner_code" rows="4">{{ ad_settings.native_banner_code or '' }}</textarea></div>
    <button type="submit">Save Ad Codes</button>
  </form>
  <hr class="section-divider">
  <h2>Add New Content</h2>
  <form method="post" action="{{ url_for('admin') }}">
    <div class="form-group"><label>Title (Required):</label><input type="text" name="title" required /></div>
    <div class="form-group"><label>Content Type:</label><select name="content_type" id="content_type" onchange="toggleEpisodeFields()"><option value="movie">Movie</option><option value="series">TV/Web Series</option></select></div>
    <div id="movie_fields">
        <div class="form-group"><label>Watch Link (Embed URL):</label><input type="url" name="watch_link" /></div><hr><p style="text-align:center; font-weight:bold;">OR Download Links</p>
        <div class="form-group"><label>480p Link:</label><input type="url" name="link_480p" /></div><div class="form-group"><label>720p Link:</label><input type="url" name="link_720p" /></div><div class="form-group"><label>1080p Link:</label><input type="url" name="link_1080p" /></div>
    </div>
    <div id="episode_fields" style="display: none;"><h3>Episodes</h3><div id="episodes_container"></div><button type="button" onclick="addEpisodeField()" class="add-episode-btn">Add Episode</button></div>
    <hr style="border-color: #333; margin: 20px 0;">
    <h3>Manual Details (Optional - Leave blank for auto-fetch)</h3>
    <div class="form-group"><label>Poster URL:</label><input type="url" name="poster_url" /></div><div class="form-group"><label>Overview:</label><textarea name="overview"></textarea></div>
    <div class="form-group"><label>Release Date (YYYY-MM-DD):</label><input type="text" name="release_date" /></div><div class="form-group"><label>Genres (Comma-separated):</label><input type="text" name="genres" /></div>
    <div class="form-group"><label>Poster Badge (e.g., 4K, Dubbed, Exclusive):</label><input type="text" name="poster_badge" /></div>
    <hr style="border-color: #333; margin: 20px 0;">
    <div class="form-group"><input type="checkbox" name="is_trending" value="true"><label for="is_trending" style="display: inline-block;">Is Trending?</label></div>
    <div class="form-group"><input type="checkbox" name="is_coming_soon" value="true"><label for="is_coming_soon" style="display: inline-block;">Is Coming Soon?</label></div>
    <button type="submit">Add Content</button>
  </form>
  <hr class="section-divider">
  <h2>Manage Content</h2>
  <table><thead><tr><th>Title</th><th>Type</th><th>Badge</th><th>Actions</th></tr></thead><tbody>
    {% for movie in all_content %}<tr><td>{{ movie.title }}</td><td>{{ movie.type | title }}</td><td>{{ movie.poster_badge or 'N/A' }}</td><td class="action-buttons"><a href="{{ url_for('edit_movie', movie_id=movie._id) }}" class="edit-btn">Edit</a><button class="delete-btn" onclick="confirmDelete('{{ movie._id }}', '{{ movie.title }}')">Delete</button></td></tr>{% endfor %}
  </tbody></table>
  {% if not all_content %}<p>No content found.</p>{% endif %}
  <hr class="section-divider">
  <h2>User Feedback / Reports</h2>
    {% if feedback_list %}
    <table><thead><tr><th>Date</th><th>Type</th><th>Title</th><th>Message</th><th>Email</th><th>Action</th></tr></thead><tbody>
      {% for item in feedback_list %}<tr><td style="min-width: 150px;">{{ item.timestamp.strftime('%Y-%m-%d %H:%M') }}</td><td>{{ item.type }}</td><td>{{ item.content_title }}</td><td style="white-space: pre-wrap; min-width: 300px;">{{ item.message }}</td><td>{{ item.email or 'N/A' }}</td><td><a href="{{ url_for('delete_feedback', feedback_id=item._id) }}" class="delete-btn" onclick="return confirm('Delete this feedback?');">Delete</a></td></tr>{% endfor %}
    </tbody></table>
    {% else %}<p>No new feedback or reports.</p>{% endif %}
  <script>
    function confirmDelete(id, title) { if (confirm('Delete "' + title + '"?')) window.location.href = '/delete_movie/' + id; }
    function toggleEpisodeFields() { var isSeries = document.getElementById('content_type').value === 'series'; document.getElementById('episode_fields').style.display = isSeries ? 'block' : 'none'; document.getElementById('movie_fields').style.display = isSeries ? 'none' : 'block'; }
    function addEpisodeField() { const c = document.getElementById('episodes_container'), d = document.createElement('div'); d.className = 'episode-item'; d.innerHTML = `<div class="form-group"><label>Ep Number:</label><input type="number" name="episode_number[]" required /></div><div class="form-group"><label>Ep Title:</label><input type="text" name="episode_title[]" required /></div><div class="form-group"><label>Watch Link:</label><input type="url" name="episode_watch_link[]" /></div><hr><p>OR Download Links</p><div class="form-group"><label>480p Link:</label><input type="url" name="episode_link_480p[]" /></div><div class="form-group"><label>720p Link:</label><input type="url" name="episode_link_720p[]" /></div><button type="button" onclick="this.parentElement.remove()" class="delete-btn" style="padding: 6px 12px;">Remove Ep</button>`; c.appendChild(d); }
    document.addEventListener('DOMContentLoaded', toggleEpisodeFields);
  </script>
</body></html>
"""
# --- END OF admin_html TEMPLATE ---


# --- START OF edit_html TEMPLATE ---
edit_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Edit Content - MovieFlix9u</title><meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { --netflix-red: #E50914; --netflix-black: #141414; --dark-gray: #222; --light-gray: #333; --text-light: #f5f5f5; }
    body { font-family: 'Roboto', sans-serif; background: var(--netflix-black); color: var(--text-light); padding: 20px; }
    h2, h3 { font-family: 'Bebas Neue', sans-serif; color: var(--netflix-red); }
    h2 { font-size: 2.5rem; margin-bottom: 20px; } h3 { font-size: 1.5rem; margin: 20px 0 10px 0;}
    form { max-width: 800px; margin: 0 auto 40px auto; background: var(--dark-gray); padding: 25px; border-radius: 8px;}
    .form-group { margin-bottom: 15px; } .form-group label { display: block; margin-bottom: 8px; font-weight: bold; }
    input, textarea, select { width: 100%; padding: 12px; border-radius: 4px; border: 1px solid var(--light-gray); font-size: 1rem; background: var(--light-gray); color: var(--text-light); box-sizing: border-box; }
    input[type="checkbox"] { width: auto; margin-right: 10px; transform: scale(1.2); }
    textarea { resize: vertical; min-height: 100px; }
    button[type="submit"], .add-episode-btn { background: var(--netflix-red); color: white; font-weight: 700; cursor: pointer; border: none; padding: 12px 25px; border-radius: 4px; font-size: 1rem; transition: background 0.3s ease; }
    button[type="submit"]:hover, .add-episode-btn:hover { background: #b00710; }
    .back-to-admin { display: inline-block; margin-bottom: 20px; color: var(--netflix-red); text-decoration: none; font-weight: bold; }
    .episode-item { border: 1px solid var(--light-gray); padding: 15px; margin-bottom: 15px; border-radius: 5px; }
    .delete-btn { background: #dc3545; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
  </style>
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
  <a href="{{ url_for('admin') }}" class="back-to-admin">← Back to Admin</a>
  <h2>Edit: {{ movie.title }}</h2>
  <form method="post">
    <div class="form-group"><label>Title:</label><input type="text" name="title" value="{{ movie.title }}" required /></div>
    <div class="form-group"><label>Content Type:</label><select name="content_type" id="content_type" onchange="toggleEpisodeFields()"><option value="movie" {% if movie.type == 'movie' %}selected{% endif %}>Movie</option><option value="series" {% if movie.type == 'series' %}selected{% endif %}>TV/Web Series</option></select></div>
    <div id="movie_fields">
        <div class="form-group"><label>Watch Link:</label><input type="url" name="watch_link" value="{{ movie.watch_link or '' }}" /></div><hr><p style="text-align:center; font-weight:bold;">OR Download Links</p>
        <div class="form-group"><label>480p Link:</label><input type="url" name="link_480p" value="{% for l in movie.links %}{% if l.quality == '480p' %}{{ l.url }}{% endif %}{% endfor %}" /></div>
        <div class="form-group"><label>720p Link:</label><input type="url" name="link_720p" value="{% for l in movie.links %}{% if l.quality == '720p' %}{{ l.url }}{% endif %}{% endfor %}" /></div>
        <div class="form-group"><label>1080p Link:</label><input type="url" name="link_1080p" value="{% for l in movie.links %}{% if l.quality == '1080p' %}{{ l.url }}{% endif %}{% endfor %}" /></div>
    </div>
    <div id="episode_fields" style="display: none;">
        <h3>Episodes</h3><div id="episodes_container">
        {% if movie.type == 'series' and movie.episodes %}{% for ep in movie.episodes | sort(attribute='episode_number') %}
        <div class="episode-item">
            <div class="form-group"><label>Ep Number:</label><input type="number" name="episode_number[]" value="{{ ep.episode_number }}" required /></div>
            <div class="form-group"><label>Ep Title:</label><input type="text" name="episode_title[]" value="{{ ep.title }}" required /></div>
            <div class="form-group"><label>Watch Link:</label><input type="url" name="episode_watch_link[]" value="{{ ep.watch_link or '' }}" /></div><hr><p>OR Download Links</p>
            <div class="form-group"><label>480p Link:</label><input type="url" name="episode_link_480p[]" value="{% for l in ep.links %}{% if l.quality=='480p'%}{{l.url}}{%endif%}{%endfor%}" /></div>
            <div class="form-group"><label>720p Link:</label><input type="url" name="episode_link_720p[]" value="{% for l in ep.links %}{% if l.quality=='720p'%}{{l.url}}{%endif%}{%endfor%}" /></div>
            <button type="button" onclick="this.parentElement.remove()" class="delete-btn">Remove Ep</button>
        </div>
        {% endfor %}{% endif %}</div><button type="button" onclick="addEpisodeField()" class="add-episode-btn">Add Episode</button>
    </div>
    <hr style="border-color: #333; margin: 20px 0;">
    <h3>Manual Details (Update or leave blank for auto-fetch)</h3>
    <div class="form-group"><label>Poster URL:</label><input type="url" name="poster_url" value="{{ movie.poster or '' }}" /></div>
    <div class="form-group"><label>Overview:</label><textarea name="overview">{{ movie.overview or '' }}</textarea></div>
    <div class="form-group"><label>Release Date:</label><input type="text" name="release_date" value="{{ movie.release_date or '' }}" /></div>
    <div class="form-group"><label>Genres:</label><input type="text" name="genres" value="{{ movie.genres|join(', ') if movie.genres else '' }}" /></div>
    <div class="form-group"><label>Poster Badge:</label><input type="text" name="poster_badge" value="{{ movie.poster_badge or '' }}" /></div>
    <hr style="border-color: #333; margin: 20px 0;">
    <div class="form-group"><input type="checkbox" name="is_trending" value="true" {% if movie.is_trending %}checked{% endif %}><label style="display: inline-block;">Is Trending?</label></div>
    <div class="form-group"><input type="checkbox" name="is_coming_soon" value="true" {% if movie.is_coming_soon %}checked{% endif %}><label style="display: inline-block;">Is Coming Soon?</label></div>
    <button type="submit">Update Content</button>
  </form>
  <script>
    function toggleEpisodeFields() { var isSeries = document.getElementById('content_type').value === 'series'; document.getElementById('episode_fields').style.display = isSeries ? 'block' : 'none'; document.getElementById('movie_fields').style.display = isSeries ? 'none' : 'block'; }
    function addEpisodeField() { const c = document.getElementById('episodes_container'), d = document.createElement('div'); d.className = 'episode-item'; d.innerHTML = `<div class="form-group"><label>Ep Number:</label><input type="number" name="episode_number[]" required /></div><div class="form-group"><label>Ep Title:</label><input type="text" name="episode_title[]" required /></div><div class="form-group"><label>Watch Link:</label><input type="url" name="episode_watch_link[]" /></div><hr><p>OR Download Links</p><div class="form-group"><label>480p Link:</label><input type="url" name="episode_link_480p[]" /></div><div class="form-group"><label>720p Link:</label><input type="url" name="episode_link_720p[]" /></div><button type="button" onclick="this.parentElement.remove()" class="delete-btn">Remove Ep</button>`; c.appendChild(d); }
    document.addEventListener('DOMContentLoaded', toggleEpisodeFields);
  </script>
</body></html>
"""
# --- END OF edit_html TEMPLATE ---


# --- START OF contact_html TEMPLATE ---
contact_html = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Contact Us / Report - MovieFlix9u</title>
    <style>
        :root { --netflix-red: #E50914; --netflix-black: #141414; --dark-gray: #222; --light-gray: #333; --text-light: #f5f5f5; }
        body { font-family: 'Roboto', sans-serif; background: var(--netflix-black); color: var(--text-light); padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .contact-container { max-width: 600px; width: 100%; background: var(--dark-gray); padding: 30px; border-radius: 8px; }
        h2 { font-family: 'Bebas Neue', sans-serif; color: var(--netflix-red); font-size: 2.5rem; text-align: center; margin-bottom: 25px; }
        .form-group { margin-bottom: 20px; } label { display: block; margin-bottom: 8px; font-weight: bold; }
        input, select, textarea { width: 100%; padding: 12px; border-radius: 4px; border: 1px solid var(--light-gray); font-size: 1rem; background: var(--light-gray); color: var(--text-light); box-sizing: border-box; }
        textarea { resize: vertical; min-height: 120px; }
        button[type="submit"] { background: var(--netflix-red); color: white; font-weight: 700; cursor: pointer; border: none; padding: 12px 25px; border-radius: 4px; font-size: 1.1rem; width: 100%; transition: background 0.3s ease; }
        button[type="submit"]:hover { background: #b00710; }
        .success-message { text-align: center; padding: 20px; background-color: #1f4e2c; color: #d4edda; border-radius: 5px; margin-bottom: 20px; }
        .back-link { display: block; text-align: center; margin-top: 20px; color: var(--netflix-red); text-decoration: none; font-weight: bold; }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
    <div class="contact-container">
        <h2>Contact Us</h2>
        {% if message_sent %}
            <div class="success-message"><p>আপনার বার্তা সফলভাবে পাঠানো হয়েছে। ধন্যবাদ!</p><p>Your message has been sent successfully. Thank you!</p></div>
            <a href="{{ url_for('home') }}" class="back-link">← Back to Home</a>
        {% else %}
            <form method="post">
                <div class="form-group"><label for="type">বিষয় (Subject):</label>
                    <select name="type" id="type">
                        <option value="Movie Request" {% if prefill_type == 'Problem Report' %}disabled{% endif %}>Movie/Series Request</option>
                        <option value="Problem Report" {% if prefill_type == 'Problem Report' %}selected{% endif %}>Report a Problem (Broken Link etc.)</option>
                        <option value="General Feedback">General Feedback</option>
                    </select>
                </div>
                <div class="form-group"><label for="content_title">মুভি/সিরিজের নাম (Title):</label><input type="text" name="content_title" id="content_title" value="{{ prefill_title }}" required></div>
                <div class="form-group"><label for="message">আপনার বার্তা (Message):</label><textarea name="message" id="message" required></textarea></div>
                <div class="form-group"><label for="email">আপনার ইমেইল (Email - Optional):</label><input type="email" name="email" id="email"></div>
                <input type="hidden" name="reported_content_id" value="{{ prefill_id }}">
                <button type="submit">Submit Message</button>
            </form>
            <a href="{{ url_for('home') }}" class="back-link">← Cancel and Go Home</a>
        {% endif %}
    </div>
</body>
</html>
"""
# --- END OF contact_html TEMPLATE ---


# ----------------- Flask Routes (Final Version) -----------------

def get_tmdb_details(movie_obj):
    if not TMDB_API_KEY: return movie_obj
    tmdb_id = movie_obj.get("tmdb_id")
    tmdb_type = "tv" if movie_obj.get("type") == "series" else "movie"
    update_fields = {}
    try:
        if not tmdb_id:
            search_url = f"https://api.themoviedb.org/3/search/{tmdb_type}?api_key={TMDB_API_KEY}&query={requests.utils.quote(movie_obj['title'])}"
            search_res = requests.get(search_url, timeout=5).json()
            if search_res.get("results"): tmdb_id = search_res["results"][0].get("id")
        if tmdb_id:
            detail_url = f"https://api.themoviedb.org/3/{tmdb_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
            res = requests.get(detail_url, timeout=5).json()
            update_fields["tmdb_id"] = tmdb_id
            if not movie_obj.get("poster") and res.get("poster_path"): update_fields["poster"] = f"https://image.tmdb.org/t/p/w500{res['poster_path']}"
            if not movie_obj.get("overview") and res.get("overview"): update_fields["overview"] = res["overview"]
            if not movie_obj.get("release_date"):
                release_date = res.get("release_date") if tmdb_type == "movie" else res.get("first_air_date")
                if release_date: update_fields["release_date"] = release_date
            if not movie_obj.get("genres") and res.get("genres"): update_fields["genres"] = [g['name'] for g in res.get("genres", [])]
            if not movie_obj.get("vote_average") and res.get("vote_average"): update_fields["vote_average"] = res.get("vote_average")
            if len(update_fields) > 1:
                movies.update_one({"_id": movie_obj["_id"]}, {"$set": update_fields})
                movie_obj.update(update_fields)
                print(f"Updated '{movie_obj['title']}' with TMDb data.")
    except requests.RequestException as e: print(f"TMDb API error for '{movie_obj['title']}': {e}")
    return movie_obj

def get_trailer_key(tmdb_id, tmdb_type):
    if not TMDB_API_KEY or not tmdb_id: return None
    try:
        video_url = f"https://api.themoviedb.org/3/{tmdb_type}/{tmdb_id}/videos?api_key={TMDB_API_KEY}"
        video_res = requests.get(video_url, timeout=5).json()
        for v in video_res.get("results", []):
            if v['type'] == 'Trailer' and v['site'] == 'YouTube': return v['key']
    except requests.RequestException: pass
    return None

def process_movie_list(movie_list):
    for item in movie_list:
        if '_id' in item: item['_id'] = str(item['_id'])
    return movie_list

@app.route('/')
def home():
    query = request.args.get('q')
    if query:
        movies_list = list(movies.find({"title": {"$regex": query, "$options": "i"}}).sort('_id', -1))
        return render_template_string(index_html, movies=process_movie_list(movies_list), query=f'Results for "{query}"', is_full_page_list=True)
    
    all_badges = movies.distinct("poster_badge")
    all_badges = sorted([badge for badge in all_badges if badge])

    limit = 12 # MODIFIED: Changed from 18 to 12
    context = {
        "trending_movies": process_movie_list(list(movies.find({"is_trending": True, "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "latest_movies": process_movie_list(list(movies.find({"type": "movie", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "latest_series": process_movie_list(list(movies.find({"type": "series", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "coming_soon_movies": process_movie_list(list(movies.find({"is_coming_soon": True}).sort('_id', -1).limit(limit))),
        "recently_added": process_movie_list(list(movies.find({"is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(6))), # For hero slider
        "recently_added_full": process_movie_list(list(movies.find({"is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))), # For carousel
        "is_full_page_list": False, "query": "", "all_badges": all_badges
    }
    return render_template_string(index_html, **context)

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie_obj = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie_obj: return "Content not found", 404
        
        movie = get_tmdb_details(dict(movie_obj))
        movie['_id'] = str(movie['_id'])
        
        related_movies = []
        if movie.get("genres"):
            related_movies = list(movies.find({"genres": {"$in": movie["genres"]}, "_id": {"$ne": ObjectId(movie_id)}}).limit(12))
        if not related_movies:
            related_movies = list(movies.find({"_id": {"$ne": ObjectId(movie_id)}, "is_coming_soon": {"$ne": True}}).sort("_id", -1).limit(12))

        trailer_key = get_trailer_key(movie.get("tmdb_id"), "tv" if movie.get("type") == "series" else "movie")
        
        return render_template_string(detail_html, movie=movie, trailer_key=trailer_key, related_movies=process_movie_list(related_movies))
    except Exception as e:
        print(f"Error in movie_detail: {e}")
        return render_template_string(detail_html, movie=None, trailer_key=None, related_movies=[])

@app.route('/watch/<movie_id>')
def watch_movie(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie: return "Content not found.", 404
        watch_link, title = movie.get("watch_link"), movie.get("title")
        episode_num = request.args.get('ep')
        if episode_num and movie.get('type') == 'series' and movie.get('episodes'):
            for ep in movie['episodes']:
                if str(ep.get('episode_number')) == episode_num:
                    watch_link, title = ep.get('watch_link'), f"{title} - E{episode_num}: {ep.get('title')}"
                    break
        if watch_link: return render_template_string(watch_html, watch_link=watch_link, title=title)
        return "Watch link not found for this content.", 404
    except Exception as e:
        print(f"Watch page error: {e}")
        return "An error occurred.", 500

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        feedback_data = {
            "type": request.form.get("type"), "content_title": request.form.get("content_title"),
            "message": request.form.get("message"), "email": request.form.get("email", "").strip(),
            "reported_content_id": request.form.get("reported_content_id"), "timestamp": datetime.utcnow()
        }
        feedback.insert_one(feedback_data)
        return render_template_string(contact_html, message_sent=True)
    prefill_title, prefill_id = request.args.get('title', ''), request.args.get('report_id', '')
    prefill_type = 'Problem Report' if prefill_id else 'Movie Request'
    return render_template_string(contact_html, message_sent=False, prefill_title=prefill_title, prefill_id=prefill_id, prefill_type=prefill_type)

@app.route('/admin', methods=["GET", "POST"])
@requires_auth
def admin():
    if request.method == "POST":
        if 'title' in request.form:
            content_type = request.form.get("content_type", "movie")
            movie_data = {
                "title": request.form.get("title"), "type": content_type,
                "is_trending": request.form.get("is_trending") == "true", "is_coming_soon": request.form.get("is_coming_soon") == "true",
                "poster": request.form.get("poster_url", "").strip(), "overview": request.form.get("overview", "").strip(),
                "release_date": request.form.get("release_date", "").strip(), "poster_badge": request.form.get("poster_badge", "").strip(),
                "genres": [g.strip() for g in request.form.get("genres", "").split(',') if g.strip()]
            }
            if content_type == "movie":
                movie_data["watch_link"] = request.form.get("watch_link", "")
                links = []
                if request.form.get("link_480p"): links.append({"quality": "480p", "url": request.form.get("link_480p")})
                if request.form.get("link_720p"): links.append({"quality": "720p", "url": request.form.get("link_720p")})
                if request.form.get("link_1080p"): links.append({"quality": "1080p", "url": request.form.get("link_1080p")})
                movie_data["links"] = links
            else: # series
                episodes = []
                for i in range(len(request.form.getlist('episode_number[]'))):
                    ep_links = []
                    if request.form.getlist('episode_link_480p[]')[i]: ep_links.append({"quality": "480p", "url": request.form.getlist('episode_link_480p[]')[i]})
                    if request.form.getlist('episode_link_720p[]')[i]: ep_links.append({"quality": "720p", "url": request.form.getlist('episode_link_720p[]')[i]})
                    episodes.append({
                        "episode_number": int(request.form.getlist('episode_number[]')[i]), "title": request.form.getlist('episode_title[]')[i],
                        "watch_link": request.form.getlist('episode_watch_link[]')[i], "links": ep_links
                    })
                movie_data["episodes"] = episodes
            movies.insert_one(movie_data)
        return redirect(url_for('admin'))
    
    all_content = process_movie_list(list(movies.find().sort('_id', -1)))
    feedback_list = process_movie_list(list(feedback.find().sort('timestamp', -1)))
    return render_template_string(admin_html, all_content=all_content, feedback_list=feedback_list)

@app.route('/admin/save_ads', methods=['POST'])
@requires_auth
def save_ads():
    ad_codes = { "popunder_code": request.form.get("popunder_code", ""), "social_bar_code": request.form.get("social_bar_code", ""), "banner_ad_code": request.form.get("banner_ad_code", ""), "native_banner_code": request.form.get("native_banner_code", "") }
    settings.update_one({}, {"$set": ad_codes}, upsert=True)
    return redirect(url_for('admin'))

@app.route('/edit_movie/<movie_id>', methods=["GET", "POST"])
@requires_auth
def edit_movie(movie_id):
    movie_obj = movies.find_one({"_id": ObjectId(movie_id)})
    if not movie_obj: return "Movie not found", 404
    if request.method == "POST":
        content_type = request.form.get("content_type", "movie")
        update_data = {
            "title": request.form.get("title"), "type": content_type,
            "is_trending": request.form.get("is_trending") == "true", "is_coming_soon": request.form.get("is_coming_soon") == "true",
            "poster": request.form.get("poster_url", "").strip(), "overview": request.form.get("overview", "").strip(),
            "release_date": request.form.get("release_date", "").strip(), "poster_badge": request.form.get("poster_badge", "").strip(),
            "genres": [g.strip() for g in request.form.get("genres", "").split(',') if g.strip()]
        }
        if content_type == "movie":
            update_data["watch_link"] = request.form.get("watch_link", "")
            links = []
            if request.form.get("link_480p"): links.append({"quality": "480p", "url": request.form.get("link_480p")})
            if request.form.get("link_720p"): links.append({"quality": "720p", "url": request.form.get("link_720p")})
            if request.form.get("link_1080p"): links.append({"quality": "1080p", "url": request.form.get("link_1080p")})
            update_data["links"] = links
            movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"episodes": ""}})
        else: # series
            episodes = []
            for i in range(len(request.form.getlist('episode_number[]'))):
                ep_links = []
                if request.form.getlist('episode_link_480p[]')[i]: ep_links.append({"quality": "480p", "url": request.form.getlist('episode_link_480p[]')[i]})
                if request.form.getlist('episode_link_720p[]')[i]: ep_links.append({"quality": "720p", "url": request.form.getlist('episode_link_720p[]')[i]})
                episodes.append({
                    "episode_number": int(request.form.getlist('episode_number[]')[i]), "title": request.form.getlist('episode_title[]')[i],
                    "watch_link": request.form.getlist('episode_watch_link[]')[i], "links": ep_links
                })
            update_data["episodes"] = episodes
            movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"links": "", "watch_link": ""}})
        movies.update_one({"_id": ObjectId(movie_id)}, {"$set": update_data})
        return redirect(url_for('admin'))
    
    movie_obj['_id'] = str(movie_obj['_id'])
    return render_template_string(edit_html, movie=movie_obj)

@app.route('/delete_movie/<movie_id>')
@requires_auth
def delete_movie(movie_id):
    movies.delete_one({"_id": ObjectId(movie_id)})
    return redirect(url_for('admin'))

@app.route('/feedback/delete/<feedback_id>')
@requires_auth
def delete_feedback(feedback_id):
    feedback.delete_one({"_id": ObjectId(feedback_id)})
    return redirect(url_for('admin'))

def render_full_list(content_list, title):
    return render_template_string(index_html, movies=process_movie_list(content_list), query=title, is_full_page_list=True)

@app.route('/badge/<badge_name>')
def movies_by_badge(badge_name):
    return render_full_list(list(movies.find({"poster_badge": badge_name}).sort('_id', -1)), f'Tag: {badge_name}')

@app.route('/genres')
def genres_page():
    all_genres = movies.distinct("genres")
    all_genres = sorted([g for g in all_genres if g])
    return render_template_string(genres_html, genres=all_genres, title="Browse by Genre")

@app.route('/genre/<genre_name>')
def movies_by_genre(genre_name):
    return render_full_list(list(movies.find({"genres": genre_name}).sort('_id', -1)), f'Genre: {genre_name}')

@app.route('/trending_movies')
def trending_movies():
    return render_full_list(list(movies.find({"is_trending": True, "is_coming_soon": {"$ne": True}}).sort('_id', -1)), "Trending Now")

@app.route('/movies_only')
def movies_only():
    return render_full_list(list(movies.find({"type": "movie", "is_coming_soon": {"$ne": True}}).sort('_id', -1)), "All Movies")

@app.route('/webseries')
def webseries():
    return render_full_list(list(movies.find({"type": "series", "is_coming_soon": {"$ne": True}}).sort('_id', -1)), "All Web Series")

@app.route('/coming_soon')
def coming_soon():
    return render_full_list(list(movies.find({"is_coming_soon": True}).sort('_id', -1)), "Coming Soon")

@app.route('/recently_added')
def recently_added_all():
    return render_full_list(list(movies.find({"is_coming_soon": {"$ne": True}}).sort('_id', -1)), "Recently Added")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
