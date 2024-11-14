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
    # Store client config in session state
    client_config = {
        "web": {
            "client_id": st.secrets["client_id"],
            "client_secret": st.secrets["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://accounts.google.com/o/oauth2/token",
            "redirect_uris": [st.secrets["redirect_uri"]],
            "javascript_origins": [st.secrets["redirect_uri"]]
        }
    }
    
    st.session_state.client_config = client_config
    
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        client_config,
        scopes=SCOPES,
    )
    
    flow.redirect_uri = st.secrets["redirect_uri"]
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=os.urandom(16).hex()  # Add state parameter for security
    )
    
    # Store state in session for verification
    st.session_state.oauth_state = state
    
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
    if 'oauth_state' not in st.session_state:
        st.session_state.oauth_state = None
    if 'client_config' not in st.session_state:
        st.session_state.client_config = None
    
    # Debug information
    query_params = st.experimental_get_query_params()
    if query_params:
        st.write("Debug - Query Parameters:", query_params)
    
    if not st.session_state.authenticated:
        if 'code' not in st.experimental_get_query_params():
            try:
                authorization_url, state = get_authorization_url()
                st.markdown(f"Please click [here]({authorization_url}) to authorize the application.")
            except Exception as e:
                st.error(f"Error generating authorization URL: {str(e)}")
        else:
            try:
                code = st.experimental_get_query_params()['code'][0]
                
                # Create flow with stored client config
                flow = google_auth_oauthlib.flow.Flow.from_client_config(
                    st.session_state.client_config,
                    scopes=SCOPES,
                )
                flow.redirect_uri = st.secrets["redirect_uri"]
                
                # Verify state if it exists in query parameters
                if 'state' in st.experimental_get_query_params():
                    received_state = st.experimental_get_query_params()['state'][0]
                    if received_state != st.session_state.oauth_state:
                        raise ValueError("State mismatch. Possible CSRF attack.")
                
                # Exchange code for tokens
                flow.fetch_token(
                    authorization_response=st.get_full_url(),
                    code=code
                )
                
                credentials = flow.credentials
                
                # Create YouTube API client to test credentials
                youtube = googleapiclient.discovery.build(
                    API_SERVICE_NAME, API_VERSION, credentials=credentials
                )
                
                # Store credentials in session state
                st.session_state.credentials = credentials
                st.session_state.youtube = youtube
                st.session_state.authenticated = True
                
                # Clear URL parameters
                st.experimental_set_query_params()
                st.rerun()
                
            except Exception as e:
                st.error(f"Authentication error: {str(e)}")
                st.error("Please try authorizing again.")
                # Reset session state
                st.session_state.authenticated = False
                if st.button("Try Again"):
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
            # Reset session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.experimental_set_query_params()
            st.rerun()

def get_full_url():
    """Helper function to get the full URL"""
    # This is a workaround since Streamlit doesn't provide direct access to the full URL
    params = st.experimental_get_query_params()
    query_string = "&".join([f"{k}={v[0]}" for k, v in params.items()])
    return f"{st.secrets['redirect_uri']}?{query_string}"

if __name__ == "__main__":
    main()
