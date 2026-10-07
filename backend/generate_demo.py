import os, random, time, requests

BASE_URL = 'http://127.0.0.1:8000'
UPLOAD_PATH = os.path.abspath(os.path.join('uploads', 'dummy.png'))

# Ensure the dummy image exists
if not os.path.isfile(UPLOAD_PATH):
    raise FileNotFoundError(f'Dummy image not found at {UPLOAD_PATH}')

# Simple random generator for lat/lon around Hyderabad
def random_location():
    lat = 17.3850 + random.uniform(-0.05, 0.05)
    lon = 78.4867 + random.uniform(-0.05, 0.05)
    return lat, lon

# Example descriptions
DESCRIPTIONS = [
    'Pothole near main road',
    'Overflowing garbage bin',
    'Streetlight flickering at night',
    'Waterlogged street after rain',
    'Damaged road surface causing accidents',
    'Broken drainage causing flooding',
    'Uncollected trash in residential area',
    'Road crack near school',
    'Streetlight not working for weeks',
    'Pothole causing traffic jam',
]

def create_complaint(session, description, lat, lon, auto_detect=True, manual_type=None):
    files = {'image': open(UPLOAD_PATH, 'rb')}
    data = {
        'description': description,
        'latitude': str(lat),
        'longitude': str(lon),
        'auto_detect': str(auto_detect).lower(),
    }
    if manual_type:
        data['manual_type'] = manual_type
    resp = session.post(f'{BASE_URL}/api/complaints/', files=files, data=data)
    return resp

if __name__ == '__main__':
    # Wait for server to be ready
    for _ in range(30):
        try:
            r = requests.get(f'{BASE_URL}/')
            if r.status_code == 200:
                print('Server ready')
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise RuntimeError('Server not reachable')

    session = requests.Session()
    created = 0
    for i in range(60):
        desc = random.choice(DESCRIPTIONS)
        lat, lon = random_location()
        resp = create_complaint(session, desc, lat, lon)
        if resp.status_code == 201:
            created += 1
            print(f'Created complaint {i+1}')
        else:
            print(f'Failed {i+1}:', resp.status_code, resp.text)
        time.sleep(0.2)  # small pause to avoid overload
    print(f'Done: {created} complaints created')
