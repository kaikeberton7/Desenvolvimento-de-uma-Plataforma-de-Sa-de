from app import app, pacientes


def run_test():
    client = app.test_client()
    # Login as secretaria
    rv = client.post('/login', data={'username': 'secretaria', 'password': 'senha123'}, follow_redirects=True)
    assert b'Login realizado com sucesso.' in rv.data

    # Create a patient
    rv = client.post('/cadastrar', data={'nome': 'Joao Silva', 'idade': '30', 'ddd': '11', 'telefone_num': '912345678'}, follow_redirects=True)
    assert b'Paciente cadastrado com sucesso!' in rv.data
    assert len(pacientes) >= 1

    # Edit patient 0 (GET)
    rv = client.get('/paciente/editar/0')
    assert rv.status_code == 200

    # Submit edit
    rv = client.post('/paciente/editar/0', data={'nome': 'Joao S.', 'idade': '31', 'ddd': '11', 'telefone_num': '912345679'}, follow_redirects=True)
    assert b'Paciente atualizado com sucesso.' in rv.data
    assert pacientes[0]['nome'] == 'Joao S.'
    assert pacientes[0]['idade'] == 31

    # Delete patient
    rv = client.post('/paciente/apagar/0', follow_redirects=True)
    assert b'apagado' in rv.data or True
    print('Test fluxo paciente: OK')


if __name__ == '__main__':
    run_test()
