import requests, os, json, time

BASE_URL = 'http://127.0.0.1:8000'
UPLOAD_PATH = os.path.abspath(os.path.join('uploads', 'dummy.png'))

def wait_server(timeout=30):
    for _ in range(timeout):
        try:
            r = requests.get(f'{BASE_URL}/')
            if r.status_code == 200:
                print('Server ready')
                return True
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError('Server not reachable')

def create_complaint():
    files = {'image': open(UPLOAD_PATH, 'rb')}
    data = {
        'description': 'Test complaint',
        'latitude': '17.3850',
        'longitude': '78.4867',
        'auto_detect': 'true',
    }
    r = requests.post(f'{BASE_URL}/api/complaints/', files=files, data=data)
    print('Create response:', r.status_code, r.json())
    return r.json()['id'] if r.status_code == 201 else None

def list_complaints():
    r = requests.get(f'{BASE_URL}/api/complaints/')
    print('List response:', r.status_code, r.json())

def get_complaint(cid):
    r = requests.get(f'{BASE_URL}/api/complaints/{cid}')
    print('Get response:', r.status_code, r.json())

def update_status(cid, status):
    r = requests.patch(f'{BASE_URL}/api/complaints/{cid}', json={'status': status})
    print('Patch response:', r.status_code, r.json())

def dashboard_summary():
    r = requests.get(f'{BASE_URL}/api/dashboard/summary')
    print('Dashboard summary:', r.status_code, r.json())

def area_stats():
    r = requests.get(f'{BASE_URL}/api/dashboard/areas')
    print('Area stats:', r.status_code, r.json())

def insights():
    r = requests.get(f'{BASE_URL}/api/dashboard/insights')
    print('Insights:', r.status_code, r.json())

if __name__ == '__main__':
    wait_server()
    cid = create_complaint()
    if cid:
        list_complaints()
        get_complaint(cid)
        update_status(cid, 'Assigned')
        get_complaint(cid)
    dashboard_summary()
    area_stats()
    insights()
