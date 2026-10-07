import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests, time

# Wait for server to be ready
for i in range(5):
    try:
        r = requests.get('http://127.0.0.1:8000/')
        if r.status_code == 200:
            print('Root OK')
            break
    except Exception:
        pass
    time.sleep(1)
else:
    print('Server not reachable')
    sys.exit(1)

# List complaints (should be empty)
resp = requests.get('http://127.0.0.1:8000/api/complaints/')
print('Complaints list status:', resp.status_code)
print('Response body:', resp.json() if resp.headers.get('content-type','').startswith('application/json') else resp.text)
