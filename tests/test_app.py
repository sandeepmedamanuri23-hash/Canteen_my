from importlib.util import module_from_spec, spec_from_file_location

spec = spec_from_file_location('canteen_app', 'app.py')
module = module_from_spec(spec)
spec.loader.exec_module(module)
app = module.app

client = app.test_client()


def test_homepage_loads():
    response = client.get('/')
    assert response.status_code == 200
    assert 'SMART PRE-ORDER' in response.get_data(as_text=True).upper()


def test_student_registration_and_login():
    email = 'alice@example.com'
    payload = {
        'name': 'Alice Student',
        'email': email,
        'password': 'secret123',
        'confirm_password': 'secret123',
        'phone': '9876543210',
    }
    reg = client.post('/register', data=payload)
    assert reg.status_code in (200, 302)
    login = client.post('/login', data={
        'email': email,
        'password': 'secret123',
    })
    assert login.status_code in (200, 302)


def test_admin_dashboard_loads():
    login = client.post('/admin/login', data={
        'email': 'admin@canteen.com',
        'password': 'Admin@123',
    })
    assert login.status_code in (200, 302)

    response = client.get('/admin/dashboard')
    assert response.status_code == 200
    assert 'ADMIN DASHBOARD' in response.get_data(as_text=True).upper()
