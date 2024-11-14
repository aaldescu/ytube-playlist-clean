# app.py
import streamlit as st
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import os
from urllib.parse import urlencode

# Streamlit config
st.set_page_config(page_title="YouTube Playlists", page_icon="▶️")

# Constants
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

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

def main():
    st.title("YouTube Playlists Viewer")
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    query_params = st.experimental_get_query_params()
    
    # Debug information
    st.write("Debug - Current URL parameters:", query_params)
    
    if not st.session_state.authenticated:
        if 'code' not in query_params:
            try:
                authorization_url, state = get_authorization_url()
                st.markdown(f"Please click [here]({authorization_url}) to authorize the application.")
                # Store state for verification
                st.session_state.state = state
            except Exception as e:
                st.error(f"Error generating authorization URL: {str(e)}")
        else:
            try:
                code = query_params['code'][0]
                
                # Create flow
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
                
                # Exchange the authorization code for credentials
                token = flow.fetch_token(
                    token_url="https://oauth2.googleapis.com/token",
                    client_secret=st.secrets["client_secret"],
                    code=code
                )
                
                # Get credentials
                credentials = flow.credentials
                
                # Create YouTube API client
                youtube = googleapiclient.discovery.build(
                    API_SERVICE_NAME, API_VERSION, credentials=credentials
                )
                
                # Store in session state
                st.session_state.youtube = youtube
                st.session_state.credentials = credentials
                st.session_state.authenticated = True
                
                # Clear URL parameters and refresh
                st.experimental_set_query_params()
                st.rerun()
                
            except Exception as e:
                st.error(f"Authentication error: {str(e)}")
                st.write("Debug - Authorization code:", code)
                if st.button("Try Again"):
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.experimental_set_query_params()
                    st.rerun()
    
    else:
        try:
            # Get playlists
            playlists = get_playlists(st.session_state.youtube)
            
            # Create dropdown
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
            
            # Logout button
            if st.button("Logout"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.experimental_set_query_params()
                st.rerun()
            
        except Exception as e:
            st.error(f"Error accessing YouTube API: {str(e)}")
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.experimental_set_query_params()
            st.rerun()

if __name__ == "__main__":
    main()
