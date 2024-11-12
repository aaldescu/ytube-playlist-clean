import streamlit as st
import google_auth_oauthlib.flow
import googleapiclient.discovery
import sqlite3
from datetime import datetime
import pandas as pd
import pickle
import os.path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import json

# OAuth 2.0 scopes required for playlist management
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

class YouTubeAuth:
    def __init__(self):
        self.creds = None
        
    def load_credentials(self):
        # Check if credentials are already stored in session state
        if 'youtube_credentials' in st.session_state:
            self.creds = st.session_state.youtube_credentials
            return True
            
        # Check if credentials are stored in token.pickle
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                self.creds = pickle.load(token)
                
        # Check if credentials are valid
        if self.creds and self.creds.valid:
            st.session_state.youtube_credentials = self.creds
            return True
            
        # If credentials exist but are expired, refresh them
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                st.session_state.youtube_credentials = self.creds
                self.save_credentials()
                return True
            except:
                return False
                
        return False
        
    def authenticate(self):
        try:
            # Load client secrets from streamlit secrets
            client_config = json.loads(st.secrets["client_config"])
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secrets.json', SCOPES)
            self.creds = flow.run_local_server(port=0)
            
            # Save credentials
            st.session_state.youtube_credentials = self.creds
            self.save_credentials()
            return True
        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            return False
            
    def save_credentials(self):
        with open('token.pickle', 'wb') as token:
            pickle.dump(self.creds, token)
            
    def get_youtube_service(self):
        if self.creds:
            return googleapiclient.discovery.build('youtube', 'v3', credentials=self.creds)
        return None

# Database setup
def init_db():
    conn = sqlite3.connect('youtube_audit.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_log
        (video_id TEXT, 
         title TEXT, 
         link TEXT, 
         channel TEXT, 
         playlist_id TEXT,
         playlist_name TEXT,
         removed_date TIMESTAMP)
    ''')
    conn.commit()
    conn.close()

# Get user's playlists
def get_playlists(youtube):
    playlists = []
    try:
        request = youtube.playlists().list(
            part="snippet,contentDetails",
            mine=True,
            maxResults=50
        )
        response = request.execute()
        
        for item in response["items"]:
            playlists.append({
                "id": item["id"],
                "title": item["snippet"]["title"],
                "count": item["contentDetails"]["itemCount"]
            })
    except Exception as e:
        st.error(f"Error fetching playlists: {str(e)}")
    return playlists

# Get playlist items
def get_playlist_items(youtube, playlist_id):
    items = []
    next_page_token = None
    
    while True:
        try:
            request = youtube.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()
            items.extend(response["items"])
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
        except Exception as e:
            st.error(f"Error fetching playlist items: {str(e)}")
            break
    
    return items

# Remove videos from playlist
def remove_videos(youtube, video_ids):
    for video_id in video_ids:
        try:
            youtube.playlistItems().delete(id=video_id).execute()
        except Exception as e:
            st.error(f"Error removing video {video_id}: {str(e)}")

# Store deleted videos in audit log
def store_audit(video_data):
    conn = sqlite3.connect('youtube_audit.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO audit_log 
        (video_id, title, link, channel, playlist_id, playlist_name, removed_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', video_data)
    conn.commit()
    conn.close()

def main():
    st.title("YouTube Playlist Cleanup Tool")
    
    # Initialize database
    init_db()
    
    # Initialize YouTube authentication
    auth = YouTubeAuth()
    
    # Check if already authenticated
    if not auth.load_credentials():
        st.warning("You need to authenticate with YouTube")
        if st.button("Authenticate"):
            if auth.authenticate():
                st.success("Authentication successful!")
                st.experimental_rerun()
            else:
                st.error("Authentication failed")
                return
        return
    
    # Get YouTube service
    youtube = auth.get_youtube_service()
    
    # Sidebar navigation
    page = st.sidebar.radio("Navigation", ["Playlist Cleanup", "Audit Log"])
    
    if page == "Playlist Cleanup":
        # Get playlists
        playlists = get_playlists(youtube)
        
        if playlists:
            playlist_options = [f"{p['title']} ({p['count']} videos)" for p in playlists]
            selected_playlist = st.selectbox(
                "Select Playlist",
                playlist_options
            )
            
            if selected_playlist:
                playlist_index = playlist_options.index(selected_playlist)
                playlist_id = playlists[playlist_index]["id"]
                playlist_name = playlists[playlist_index]["title"]
                
                # Get playlist items
                items = get_playlist_items(youtube, playlist_id)
                
                if items:
                    # Create DataFrame
                    df = pd.DataFrame([{
                        'video_id': item['id'],
                        'title': item['snippet']['title'],
                        'channel': item['snippet']['channelTitle'],
                        'link': f"https://youtube.com/watch?v={item['snippet']['resourceId']['videoId']}"
                    } for item in items])
                    
                    # Filters
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        search_term = st.text_input("Search in title")
                    
                    with col2:
                        channel_filter = st.multiselect(
                            "Filter by channel",
                            options=sorted(df['channel'].unique())
                        )
                    
                    # Apply filters
                    filtered_df = df.copy()
                    if search_term:
                        filtered_df = filtered_df[filtered_df['title'].str.contains(search_term, case=False)]
                    if channel_filter:
                        filtered_df = filtered_df[filtered_df['channel'].isin(channel_filter)]
                    
                    # Display videos
                    st.write(f"Showing {len(filtered_df)} videos")
                    st.dataframe(filtered_df[['title', 'channel', 'link']])
                    
                    # Select videos to remove
                    selected_videos = st.multiselect(
                        "Select videos to remove",
                        options=filtered_df.index,
                        format_func=lambda x: filtered_df.loc[x, 'title']
                    )
                    
                    if st.button("Remove Selected Videos"):
                        if selected_videos:
                            if st.warning("Are you sure you want to remove these videos?"):
                                # Store in audit log
                                for idx in selected_videos:
                                    video_data = (
                                        filtered_df.loc[idx, 'video_id'],
                                        filtered_df.loc[idx, 'title'],
                                        filtered_df.loc[idx, 'link'],
                                        filtered_df.loc[idx, 'channel'],
                                        playlist_id,
                                        playlist_name,
                                        datetime.now()
                                    )
                                    store_audit(video_data)
                                
                                # Remove videos
                                video_ids = filtered_df.loc[selected_videos, 'video_id'].tolist()
                                remove_videos(youtube, video_ids)
                                st.success("Videos removed successfully!")
                                st.experimental_rerun()
                
                else:
                    st.warning("No videos found in this playlist")
        else:
            st.error("No playlists found")
    
    else:  # Audit Log page
        st.header("Audit Log")
        
        conn = sqlite3.connect('youtube_audit.db')
        audit_df = pd.read_sql_query("SELECT * FROM audit_log", conn)
        conn.close()
        
        if not audit_df.empty:
            # Add filter for audit log
            date_filter = st.date_input("Filter by date", value=None)
            if date_filter:
                audit_df['date'] = pd.to_datetime(audit_df['removed_date']).dt.date
                audit_df = audit_df[audit_df['date'] == date_filter]
            
            st.dataframe(audit_df)
            
            # Export to CSV
            if st.button("Export to CSV"):
                csv = audit_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="youtube_audit_log.csv",
                    mime="text/csv"
                )
        else:
            st.info("No audit records found")

if __name__ == "__main__":
    main()
