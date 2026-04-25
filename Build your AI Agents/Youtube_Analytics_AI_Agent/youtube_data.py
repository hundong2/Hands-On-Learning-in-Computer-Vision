# YouTube Video Tracking System - Updated JSON Structure
from dotenv import dotenv_values
import os
import json
from datetime import datetime
from googleapiclient.discovery import build
from typing import Dict, Any, List

# Load environment variables
API = dotenv_values('.env')
YT_API_KEY = API['YT_API_KEY']

# YouTube Data API v3 서비스 객체를 생성하는 함수입니다.
# API 키를 이용해 유튜브 서버와 통신할 수 있는 클라이언트를 만들어 반환합니다.
def get_youtube_service():
    """Get YouTube Data API v3 service"""
    return build('youtube', 'v3', developerKey=YT_API_KEY)

# 특정 유튜브 동영상 ID를 받아 현재 조회수, 좋아요 수, 댓글 수 등의 통계를 가져오는 함수입니다.
# 동영상을 찾지 못하거나 오류가 발생하면 에러 정보를 담은 딕셔너리를 반환합니다.
def get_video_analytics(video_id: str) -> Dict[str, Any]:
    """
    Get current analytics for a specific YouTube video.
    
    Args:
        video_id (str): The YouTube video ID
        
    Returns:
        Dict[str, Any]: Dictionary containing video analytics data
    """
    youtube = get_youtube_service()
    
    try:
        request = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=video_id
        )
        response = request.execute()
        
        if not response['items']:
            return {"error": "Video not found"}
            
        video_data = response['items'][0]
        
        analytics = {
            "timestamp": datetime.now().isoformat(),
            "video_id": video_id,
            "title": video_data['snippet']['title'],
            "channel_title": video_data['snippet']['channelTitle'],
            "published_at": video_data['snippet']['publishedAt'],
            "view_count": int(video_data['statistics'].get('viewCount', 0)),
            "like_count": int(video_data['statistics'].get('likeCount', 0)),
            "comment_count": int(video_data['statistics'].get('commentCount', 0))
        }
        
        return analytics
        
    except Exception as e:
        return {"error": f"Failed to fetch video data: {str(e)}"}

# 여러 개의 유튜브 동영상 ID 목록을 받아, 각 동영상의 통계를 한 번에 수집하는 함수입니다.
# 수집에 성공한 동영상의 데이터만 리스트로 반환합니다.
def track_multiple_videos(video_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Get analytics for multiple videos at once.
    
    Args:
        video_ids (List[str]): List of YouTube video IDs
        
    Returns:
        List[Dict[str, Any]]: List of video analytics
    """
    all_analytics = []
    
    print(f"Tracking {len(video_ids)} videos...")
    
    for i, video_id in enumerate(video_ids, 1):
        print(f"  {i}/{len(video_ids)} - Fetching {video_id}")
        
        try:
            analytics = get_video_analytics(video_id)
            
            if 'error' not in analytics:
                all_analytics.append(analytics)
            else:
                print(f"    Error: {analytics['error']}")
                
        except Exception as e:
            print(f"    Exception occurred: {str(e)}")
    
    print(f"Successfully tracked {len(all_analytics)} videos\n")
    return all_analytics

# 수집한 유튜브 통계 데이터를 JSON 파일(데이터베이스)에 저장하는 함수입니다.
# 동영상 ID를 키(key)로 사용하고, 시간별 데이터 포인트를 목록으로 누적 저장합니다.
# 파일이 이미 있으면 기존 데이터에 새 데이터를 추가(append)합니다.
def save_to_database(analytics_data: List[Dict[str, Any]], database_file: str = "youtube_tracking.json"):
    """
    Save analytics data to JSON database organized by video_id as keys.
    Each video_id contains a list of timestamped data points.
    
    Structure:
    {
        "video_id_1": [
            {"timestamp": "2024-01-01T10:00:00", "title": "Video Title", ...},
            {"timestamp": "2024-01-02T10:00:00", "title": "Video Title", ...}
        ],
        "video_id_2": [...]
    }
    
    Args:
        analytics_data: List of analytics data to save
        database_file: Database file name
    """
    # Load existing data
    if os.path.exists(database_file):
        with open(database_file, 'r', encoding='utf-8') as f:
            database = json.load(f)
    else:
        database = {}
    
    # Organize new data by video_id
    for analytics in analytics_data:
        video_id = analytics.get('video_id')
        if not video_id:
            continue
            
        # Remove video_id from the data since it's now the key
        video_data = {k: v for k, v in analytics.items() if k != 'video_id'}
        
        # Initialize video entry if doesn't exist
        if video_id not in database:
            database[video_id] = []
        
        # Append new data point
        database[video_id].append(video_data)
    
    # Save back to file
    with open(database_file, 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=2, ensure_ascii=False)
    
    # Calculate total records
    total_records = sum(len(video_data) for video_data in database.values())
    
    print(f"Data saved to {database_file}")
    print(f"Total videos in database: {len(database)}")
    print(f"Total data points: {total_records}\n")

# JSON 데이터베이스 파일의 요약 정보를 출력하는 함수입니다.
# 저장된 동영상 수, 전체 데이터 포인트 수, 각 동영상의 최신 조회수 등을 보여줍니다.
def get_database_summary(database_file: str = "youtube_tracking.json"):
    """
    Display a summary of the database structure and contents.
    
    Args:
        database_file: Database file name
    """
    if not os.path.exists(database_file):
        print("No database found yet. Run tracking to create it.")
        return
    
    with open(database_file, 'r', encoding='utf-8') as f:
        database = json.load(f)
    
    if not database:
        print("Database is empty")
        return
    
    print("=" * 50)
    print("DATABASE SUMMARY")
    print("=" * 50)
    
    total_data_points = sum(len(video_data) for video_data in database.values())
    print(f"Total Videos: {len(database)}")
    print(f"Total Data Points: {total_data_points}")
    print()
    
    for video_id, data_points in database.items():
        if data_points:  # Check if list is not empty
            latest = data_points[-1]  # Get most recent data point
            print(f"📹 {latest.get('title', 'Unknown Title')}")
            print(f"   Video ID: {video_id}")
            print(f"   Channel: {latest.get('channel_title', 'Unknown')}")
            print(f"   Data Points: {len(data_points)}")
            print(f"   Latest Views: {latest.get('view_count', 0):,}")
            print(f"   Last Updated: {latest.get('timestamp', 'Unknown')}")
            print()

# ----------------------------------------------------------------
# Main execution
# 유튜브 데이터 수집 전체 과정을 실행하는 함수입니다.
# 동영상 목록을 받아 데이터를 수집하고, JSON 파일에 저장한 뒤, 결과 요약을 출력합니다.
def youtube_data_collection(VIDEO_IDS: List[str]):
    
    print("YouTube Video Data Collection System")
    print("=" * 50)
    
    # Track all videos
    current_data = track_multiple_videos(VIDEO_IDS)
    
    # Save to database with new structure
    if current_data:
        save_to_database(current_data)
        
        # Show current session results
        print("Current Session Results:")
        for video in current_data:
            print(f"  📹 {video['title']}")
            print(f"     Views: {video['view_count']:,}")
            print(f"     Likes: {video['like_count']:,}")
            print(f"     Comments: {video['comment_count']:,}")
            print()
    
    # Show database summary
    get_database_summary()
    
    print("Data collection completed!")
    print("=" * 50, "\n")