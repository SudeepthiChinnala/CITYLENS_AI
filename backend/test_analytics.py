import requests, os, time
BASE_URL = 'http://127.0.0.1:8000'

def wait_server():
    for _ in range(30):
        try:
            r = requests.get(f'{BASE_URL}/')
            if r.status_code == 200:
                print('Server ready')
                return True
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError('Server not reachable')

def get_clusters():
    r = requests.get(f'{BASE_URL}/api/dashboard/clusters')
    print('Clusters response:', r.status_code)
    if r.status_code == 200:
        print(r.json())

def get_areas():
    r = requests.get(f'{BASE_URL}/api/dashboard/areas')
    print('Areas response:', r.status_code)
    if r.status_code == 200:
        print(r.json())

def get_insights():
    r = requests.get(f'{BASE_URL}/api/dashboard/insights')
    print('Insights response:', r.status_code)
    if r.status_code == 200:
        print(r.json())

if __name__ == '__main__':
    wait_server()
    get_clusters()
    get_areas()
    get_insights()
