from app import app


def test_login(username, password):
    client = app.test_client()
    rv = client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)
    with client.session_transaction() as sess:
        user = sess.get('username')
        role = sess.get('role')
    success_msg = b'Login realizado com sucesso.' in rv.data
    failed_msg = b'Usu\xc3\xa1rio ou senha inv\xc3\xa1lidos.' in rv.data
    return rv.status_code, user, role, success_msg, failed_msg


def main():
    tests = [
        ('secretaria', 'senha123'),
        ('medico', 'med123'),
        ('secretaria', 'errada'),
        ('Secretaria', 'senha123'),
        (' secretaria ', 'senha123')
    ]
    for u, p in tests:
        status, user, role, ok, fail = test_login(u, p)
        print(f"Teste login {u!r}: status={status}, session_user={user}, role={role}, success={ok}, failed={fail}")


if __name__ == '__main__':
    main()
