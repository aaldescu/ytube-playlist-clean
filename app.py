# app.py
import streamlit as st
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import os
from urllib.parse import urlencode
import json
import pickle
from pathlib import Path

# Streamlit config
st.set_page_config(page_title="YouTube Playlists", page_icon="▶️")

# Constants
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
CREDENTIALS_FILE = '.credentials/youtube_credentials.pickle'

def ensure_credentials_dir():
    """Ensure the credentials directory exists"""
    Path('.credentials').mkdir(exist_ok=True)

def save_credentials(credentials):
    """Save credentials to file"""
    ensure_credentials_dir()
    with open(CREDENTIALS_FILE, 'wb') as f:
        pickle.dump(credentials_to_dict(credentials), f)

def load_credentials():
    """Load credentials from file"""
    try:
        with open(CREDENTIALS_FILE, 'rb') as f:
            credentials_dict = pickle.load(f)
            return google.oauth2.credentials.Credentials(**credentials_dict)
    except (FileNotFoundError, EOFError):
        return None

def credentials_to_dict(credentials):
    """Convert credentials to dictionary"""
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

def get_authorization_url():
    """Get the authorization URL for OAuth2"""
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        {
            "web": {
                "client_id": st.secrets["client_id"],
                "client_secret": st.secrets["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [st.secrets["redirect_uri"]]
            }
        },
        scopes=SCOPES
    )
    
    flow.redirect_uri = st.secrets["redirect_uri"]
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    return authorization_url, state

def get_playlists(youtube):
    """Get all playlists for the authenticated user"""
    request = youtube.playlists().list(
        part="snippet",
        mine=True,
        maxResults=50
    )
    response = request.execute()
    
    playlists = []
    for item in response.get('items', []):
        playlist = {
            'id': item['id'],
            'title': item['snippet']['title']
        }
        playlists.append(playlist)
    
    return playlists

def initialize_youtube_client(credentials):
    """Initialize YouTube client with credentials"""
    try:
        return googleapiclient.discovery.build(
            API_SERVICE_NAME, API_VERSION, credentials=credentials
        )
    except Exception as e:
        st.error(f"Error initializing YouTube client: {str(e)}")
        return None

def main():
    st.title("YouTube Playlists Viewer")
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'credentials' not in st.session_state:
        st.session_state.credentials = None
    if 'youtube' not in st.session_state:
        st.session_state.youtube = None
    
    # Try to load credentials if not authenticated
    if not st.session_state.authenticated:
        credentials = load_credentials()
        if credentials and credentials.valid:
            youtube = initialize_youtube_client(credentials)
            if youtube:
                st.session_state.update({
                    'authenticated': True,
                    'credentials': credentials,
                    'youtube': youtube
                })
        elif credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(google.auth.transport.requests.Request())
                youtube = initialize_youtube_client(credentials)
                if youtube:
                    st.session_state.update({
                        'authenticated': True,
                        'credentials': credentials,
                        'youtube': youtube
                    })
                    save_credentials(credentials)
            except Exception as e:
                st.error(f"Error refreshing credentials: {str(e)}")
    
    query_params = st.experimental_get_query_params()
    
    # Debug information
    with st.expander("Debug Information"):
        st.write("Current URL parameters:", query_params)
        st.write("Session State Contents:")
        for key, value in st.session_state.items():
            if key in ['youtube', 'credentials']:
                st.write(f"{key}: <object>")
            else:
                st.write(f"{key}: {value}")
    
    # Handle OAuth callback
    if not st.session_state.authenticated and 'code' in query_params:
        try:
            code = query_params['code'][0]
            received_state = query_params.get('state', [None])[0]
            
            if 'state' in st.session_state and received_state != st.session_state.state:
                st.error("State mismatch. Possible security issue.")
                raise ValueError("State mismatch")
            
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                {
                    "web": {
                        "client_id": st.secrets["client_id"],
                        "client_secret": st.secrets["client_secret"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [st.secrets["redirect_uri"]]
                    }
                },
                scopes=SCOPES
            )
            flow.redirect_uri = st.secrets["redirect_uri"]
            
            flow.fetch_token(
                code=code,
                client_secret=st.secrets["client_secret"],
            )
            
            credentials = flow.credentials
            youtube = initialize_youtube_client(credentials)
            
            if youtube:
                st.session_state.update({
                    'authenticated': True,
                    'credentials': credentials,
                    'youtube': youtube
                })
                save_credentials(credentials)
            
            st.experimental_set_query_params()
            
        except Exception as e:
            st.error(f"Authentication error: {str(e)}")
            if st.button("Try Again"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.experimental_set_query_params()
                st.rerun()
    
    # Show authorization URL if not authenticated
    if not st.session_state.authenticated:
        try:
            authorization_url, state = get_authorization_url()
            st.markdown(f"Please click [here]({authorization_url}) to authorize the application.")
            st.session_state.state = state
        except Exception as e:
            st.error(f"Error generating authorization URL: {str(e)}")
    
    # Show playlists if authenticated
    if st.session_state.authenticated and st.session_state.youtube:
        try:
            playlists = get_playlists(st.session_state.youtube)
            
            if playlists:
                playlist_titles = [playlist['title'] for playlist in playlists]
                selected_playlist = st.selectbox(
                    "Select a playlist:",
                    playlist_titles
                )
                
                if selected_playlist:
                    selected_playlist_id = next(
                        playlist['id'] for playlist in playlists 
                        if playlist['title'] == selected_playlist
                    )
                    st.write(f"Selected playlist ID: {selected_playlist_id}")
            else:
                st.write("No playlists found.")
            
            if st.button("Logout"):
                # Remove credentials file
                if os.path.exists(CREDENTIALS_FILE):
                    os.remove(CREDENTIALS_FILE)
                
                # Clear session state
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.experimental_set_query_params()
                st.rerun()
            
        except Exception as e:
            st.error(f"Error accessing YouTube API: {str(e)}")
            # Remove credentials file
            if os.path.exists(CREDENTIALS_FILE):
                os.remove(CREDENTIALS_FILE)
            
            # Clear session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.experimental_set_query_params()
            st.rerun()

if __name__ == "__main__":
    main()
