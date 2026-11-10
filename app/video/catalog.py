"""Bundled, openly licensed video sources. No arbitrary local paths are accepted."""
from app.config import ROOT

VIDEOS = {
    'worker-zone': {'file': 'worker-zone-detection.mp4', 'name': 'Workshop · PPE checkpoint', 'location': 'Recorded workshop footage'},
    'people': {'file': 'people-detection.mp4', 'name': 'Walkway · people & zones', 'location': 'Recorded pedestrian footage'},
    'walkthrough': {'file': 'one-by-one-person-detection.mp4', 'name': 'Entrance · individual PPE check', 'location': 'Recorded entrance footage'},
}

def video_path(key):
    item = VIDEOS.get(key)
    return ROOT / 'frontend/assets/videos' / item['file'] if item else None

def samples():
    return [{'id': key, **value, 'available': video_path(key).is_file(),
             'credit': 'Intel IoT DevKit sample-videos · CC BY 4.0',
             'source_url': 'https://github.com/intel-iot-devkit/sample-videos'} for key, value in VIDEOS.items()]
