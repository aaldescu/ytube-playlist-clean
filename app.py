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
        prompt='consent'  # Force to get refresh_token
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

def create_youtube_client(credentials):
    """Create YouTube API client from credentials"""
    return googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, credentials=credentials
    )

def main():
    st.title("YouTube Playlists Viewer")
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'credentials' not in st.session_state:
        st.session_state.credentials = None
    
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
                            "redirect_uris": [st.secrets["redirect_uri"]]
                        }
                    },
                    scopes=SCOPES
                )
                flow.redirect_uri = st.secrets["redirect_uri"]
                flow.fetch_token(code=code)
                
                # Get credentials and store them
                credentials = flow.credentials
                st.session_state.credentials = {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes
                }
                
                st.session_state.authenticated = True
                st.rerun()
                
            except Exception as e:
                st.error(f"An error occurred during authentication: {str(e)}")
    
    else:
        try:
            # Recreate credentials object
            credentials = google.oauth2.credentials.Credentials(
                token=st.session_state.credentials['token'],
                refresh_token=st.session_state.credentials['refresh_token'],
                token_uri=st.session_state.credentials['token_uri'],
                client_id=st.session_state.credentials['client_id'],
                client_secret=st.session_state.credentials['client_secret'],
                scopes=st.session_state.credentials['scopes']
            )
            
            # Create YouTube API client
            youtube = create_youtube_client(credentials)
            
            # Get playlists
            playlists = get_playlists(youtube)
            
            # Update stored credentials if they were refreshed
            if credentials.token != st.session_state.credentials['token']:
                st.session_state.credentials['token'] = credentials.token
            
            # Create dropdown
            if playlists:
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
            else:
                st.write("No playlists found.")
            
            # Add logout button
            if st.button("Logout"):
                st.session_state.authenticated = False
                st.session_state.credentials = None
                st.rerun()
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.session_state.authenticated = False
            st.session_state.credentials = None
            st.rerun()

if __name__ == "__main__":
    main()
