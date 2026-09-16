from importlib.util import module_from_spec, spec_from_file_location

spec = spec_from_file_location('canteen_app', 'app.py')
module = module_from_spec(spec)
spec.loader.exec_module(module)
app = module.app

client = app.test_client()

home = client.get('/')
print('HOME', home.status_code, 'CANTEEN' in home.get_data(as_text=True).upper())

reg = client.post('/register', data={
    'name': 'Alice Student',
    'email': 'alice@example.com',
    'password': 'secret123',
    'confirm_password': 'secret123',
    'phone': '9876543210',
})
print('REG', reg.status_code)
print(reg.headers.get('Location'))

login = client.post('/login', data={
    'email': 'alice@example.com',
    'password': 'secret123',
})
print('LOGIN', login.status_code)
print(login.headers.get('Location'))
