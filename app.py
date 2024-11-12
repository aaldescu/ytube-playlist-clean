# app.py
import streamlit as st
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import os
from pathlib import Path

# Streamlit config
st.set_page_config(page_title="YouTube Playlists", page_icon="▶️")

# Constants
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

def create_credentials():
    """Create credentials object from secrets"""
    credentials = google.oauth2.credentials.Credentials(
        token=None,
        client_id=st.secrets["client_id"],
        client_secret=st.secrets["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES
    )
    return credentials

def get_authorization_url():
    """Get the authorization URL for OAuth2"""
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        {
            "web": {
                "client_id": st.secrets["client_id"],
                "client_secret": st.secrets["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES
    )
    
    flow.redirect_uri = st.secrets["redirect_uri"]
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
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
    
    if not st.session_state.authenticated:
        if 'code' not in st.experimental_get_query_params():
            authorization_url, state = get_authorization_url()
            st.markdown(f"Please click [here]({authorization_url}) to authorize the application.")
        else:
            try:
                code = st.experimental_get_query_params()['code'][0]
                flow = google_auth_oauthlib.flow.Flow.from_client_config(
                    {
                        "web": {
                            "client_id": st.secrets["client_id"],
                            "client_secret": st.secrets["client_secret"],
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                        }
                    },
                    scopes=SCOPES
                )
                flow.redirect_uri = st.secrets["redirect_uri"]
                flow.fetch_token(code=code)
                credentials = flow.credentials
                
                # Create YouTube API client
                youtube = googleapiclient.discovery.build(
                    API_SERVICE_NAME, API_VERSION, credentials=credentials)
                
                st.session_state.youtube = youtube
                st.session_state.authenticated = True
                st.experimental_rerun()
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
    
    else:
        try:
            # Get playlists
            playlists = get_playlists(st.session_state.youtube)
            
            # Create dropdown
            playlist_titles = [playlist['title'] for playlist in playlists]
            selected_playlist = st.selectbox(
                "Select a playlist:",
                playlist_titles
            )
            
            # Display selected playlist info
            if selected_playlist:
                selected_playlist_id = next(
                    playlist['id'] for playlist in playlists 
                    if playlist['title'] == selected_playlist
                )
                st.write(f"Selected playlist ID: {selected_playlist_id}")
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.session_state.authenticated = False

if __name__ == "__main__":
    main()
