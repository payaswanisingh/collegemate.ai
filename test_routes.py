from app import app

with app.test_client() as c:
    r = c.get('/')
    print('GET / status:', r.status_code)
    r2 = c.get('/index.html')
    print('GET /index.html status:', r2.status_code)
    r3 = c.get('/health')
    print('GET /health status:', r3.status_code)
