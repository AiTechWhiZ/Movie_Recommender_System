import streamlit as st
import pickle
import pandas as pd
import requests
from functools import lru_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# create a requests Session with retries (mounted once)
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.6, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)
session.mount("http://", adapter)

@lru_cache(maxsize=512)
def fetch_poster(movie_id):
    placeholder = "https://via.placeholder.com/500x750?text=No+Image"
    try:
        movie_id = int(movie_id)
    except Exception:
        return placeholder
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key=b7b9fae52595274479c98afab8c90ea3&language=en-US"
        response = session.get(url, timeout=10)
        if response.status_code == 404:
            return placeholder
        response.raise_for_status()
        data = response.json()
        poster_path = data.get('poster_path')
        if poster_path:
            return "https://image.tmdb.org/t/p/w500/" + poster_path
        return placeholder
    except requests.exceptions.RequestException as e:
        print("TMDB request failed:", e)
        return placeholder

@lru_cache(maxsize=512)
def fetch_details(movie_id):
    try:
        movie_id = int(movie_id)
    except Exception:
        return {}
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key=b7b9fae52595274479c98afab8c90ea3&language=en-US"
        response = session.get(url, timeout=10)
        response.raise_for_status()
        d = response.json()
        genres = ", ".join(g.get("name","") for g in d.get("genres", []))
        return {
            "overview": d.get("overview"),
            "genres": genres,
            "release_date": d.get("release_date") or d.get("first_air_date"),
            "rating": d.get("vote_average"),
            "homepage": d.get("homepage"),
        }
    except requests.exceptions.RequestException:
        return {}

def recommend(movie, progress_callback=None):
    movie_index = movies[movies['title'] == movie].index[0]
    distances = similarity[movie_index]
    movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:11]

    recommended_movies = []
    recommended_movies_posters = []
    total = len(movies_list)
    for idx, i in enumerate(movies_list):
        row = movies.iloc[i[0]]
        movie_id = row.get('movie_id') or row.get('id') or row.get('tmdb_id') or row.get('movieId')
        if movie_id is None:
            if progress_callback:
                progress_callback(int((idx + 1) / total * 100))
            continue
        recommended_movies.append(row.get('title') or row.get('name') or "Unknown title")
        poster_url = fetch_poster(movie_id) or "https://via.placeholder.com/500x750?text=No+Image"
        recommended_movies_posters.append(poster_url)
        if progress_callback:
            progress_callback(int((idx + 1) / total * 100))
    return recommended_movies, recommended_movies_posters


try:
    movies_dict = pickle.load(open("movie_dict.pkl", "rb"))
    movies = pd.DataFrame(movies_dict)
except FileNotFoundError:
    st.error("movie_dict.pkl not found in the app folder. Place the file in c:\\Project or update the path.")
    st.stop()

try:
    similarity = pickle.load(open("similarity.pkl", "rb"))
except FileNotFoundError:
    st.error("similarity.pkl not found in the app folder. Place the file in c:\\Project or update the path.")
    st.stop()


st.title("Movie Recommender System")

# load query params to allow shareable links like ?movie=The+Matrix
params = st.query_params
initial_movie = params.get("movie", [None])[0]
select_index = 0
if initial_movie:
    try:
        select_index = int(movies[movies['title'] == initial_movie].index[0])
    except Exception:
        select_index = 0

selected_movie_name = st.selectbox("Select a Movie", movies['title'].values, index=select_index)

# small responsive grid and lazy-loading CSS
st.markdown(
    """
    <style>
    .rec-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:12px; }
    .rec-card { text-align:center; padding:6px; }
    .rec-title { font-weight:600; font-size:14px; line-height:1.1; word-wrap:break-word; margin-top:6px; }
    .rec-img { width:100%; height:auto; border-radius:6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

if st.button("Recommend"):
    # spinner + progress bar while fetching
    with st.spinner("Fetching recommendations..."):
        progress_bar = st.progress(0)
        def _progress(p):
            progress_bar.progress(p)
        names, posters = recommend(selected_movie_name, progress_callback=_progress)

    # export CSV (no details columns)
    df_export = pd.DataFrame({
        "title": names,
        "poster": posters,
    })
    csv_bytes = df_export.to_csv(index=False).encode("utf-8")
    st.download_button("Download recommendations (CSV)", csv_bytes, file_name=f"Recommendations_for_{selected_movie_name}.csv", mime="text/csv")

    # Render responsive grid. lazy-loading posters, no details buttons
    n = min(len(names), len(posters), 8)
    grid_html = "<div class='rec-grid'>"
    for idx in range(n):
        grid_html += "<div class='rec-card'>"
        grid_html += f"<img class='rec-img' src='{posters[idx]}' loading='lazy' alt='poster'/>"
        grid_html += f"<div class='rec-title'>{names[idx]}</div>"
        grid_html += "</div>"
    grid_html += "</div>"

    st.markdown(grid_html, unsafe_allow_html=True)
#




