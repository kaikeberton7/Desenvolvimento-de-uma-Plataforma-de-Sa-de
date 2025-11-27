

# --- IMPORTS NECESSÁRIOS ---
from flask import Flask, render_template, request, redirect, url_for, flash, session
import json
import os
from datetime import datetime, date, timedelta
from functools import wraps
import re

def format_cpf(cpf_raw):
    cpf = only_digits(cpf_raw)


# Dados dos pacientes
pacientes = []

# Fila de atendimento
fila = []

# Agendamentos
agendamentos = []
# Receitas (prescrições)
receitas = []
# Disponibilidades definidas pelo médico
disponibilidades = []



# --- Flask app e arquivo de dados ---
app = Flask(__name__)
app.secret_key = 'clinica-vida-mais'
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')
# Carrega usuários do arquivo users.json, se existir
USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')
if os.path.exists(USERS_FILE):
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            USERS = json.load(f)
    except Exception:
        USERS = {
            'secretaria': {'password': 'senha123', 'role': 'secretaria'},
            'medico': {'password': 'med123', 'role': 'medico'}
        }

# Decorators
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                flash('Acesso negado.', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapper
    return deco


# --- Pagamentos: exibir e editar status ---

@app.route('/pagamentos/editar/<int:idx>', methods=['POST'])
@login_required
@roles_required('secretaria', 'medico')
def editar_pagamento(idx):
    novo_status = request.form.get('novo_status')
    if idx < 0 or idx >= len(pacientes):
        flash('Paciente não encontrado.', 'error')
        return redirect(url_for('pagamentos'))
    if novo_status not in ['Em dia', 'Pendente', 'Atrasado', 'Plano']:
        flash('Status inválido.', 'error')
        return redirect(url_for('pagamentos'))

    pacientes[idx]['pagamento_em_dia'] = novo_status
    save_data()
    flash('Status de pagamento atualizado.', 'success')
    return redirect(url_for('pagamentos'))


# --- Funções auxiliares ---
def load_data():
    global pacientes, fila
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            pacientes = data.get('pacientes', [])
            fila = data.get('fila', [])
            agendamentos[:] = data.get('agendamentos', [])
            receitas[:] = data.get('receitas', [])
            disponibilidades[:] = data.get('disponibilidades', [])
        except Exception:
            pacientes = []
            fila = []
    else:
        pacientes = []
        fila = []

# Chamar load_data após definição

load_data()



def save_data():
    try:
        data = {'pacientes': pacientes, 'fila': fila, 'agendamentos': agendamentos, 'receitas': receitas, 'disponibilidades': disponibilidades}
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# --- Validators for CPF and RG ---
def only_digits(s):
    return ''.join(ch for ch in (s or '') if ch.isdigit())

def validate_cpf(cpf_raw):
    cpf = only_digits(cpf_raw)
    if len(cpf) != 11:
        return False
    # Reject sequences of same digit
    if cpf == cpf[0] * 11:
        return False
    # first check digit
    def calc_digit(cpf, length):
        s = sum(int(cpf[i]) * (length + 1 - i) for i in range(length))
        r = (s * 10) % 11
        return 0 if r == 10 else r
    d1 = calc_digit(cpf, 9)
    d2 = calc_digit(cpf, 10)
    return d1 == int(cpf[9]) and d2 == int(cpf[10])

def validate_rg(rg_raw):
    # RG formats vary by state; basic validation: digits only and length between 7 and 9
    rg = only_digits(rg_raw)
    return 7 <= len(rg) <= 9


# Formatter for CPF display

def format_cpf(cpf_raw):
    cpf = only_digits(cpf_raw)
    if len(cpf) == 11:
        return f"{cpf[0:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:11]}"
    return cpf_raw or ''

# Rota para fila de atendimento
@app.route('/fila', methods=['GET', 'POST'])
@login_required
@roles_required('secretaria')
def fila_atendimento():
    global fila
    mensagem = ''
    if request.method == 'POST':
        if 'inserir' in request.form:
            nome = request.form.get('nome', '').strip()
            cpf = request.form.get('cpf', '').strip()
            tipo = request.form.get('tipo', 'normal')
            if not nome or not cpf:
                mensagem = 'Preencha todos os campos.'
            elif len(fila) >= 3:
                mensagem = 'Fila cheia (máx 3 pessoas).'
            else:
                paciente = {
                    'nome': nome,
                    'cpf_display': format_cpf(cpf),
                    'tipo': tipo,
                    'emergencia': tipo == 'emergencia'
                }
                if paciente['emergencia']:
                    fila.insert(0, paciente)
                else:
                    fila.append(paciente)
                save_data()
        elif 'remover_and_next' in request.form:
            if fila:
                fila.pop(0)
                save_data()
    return render_template('fila.html', fila=fila, mensagem=mensagem)




# Expose validators and formatters to Jinja templates
app.jinja_env.globals['validate_cpf'] = validate_cpf
app.jinja_env.globals['validate_rg'] = validate_rg
app.jinja_env.globals['format_cpf'] = format_cpf


# Formatter for display of agendamento datetimes
def format_datetime_display(dt_str):
    if not dt_str:
        return ''
    try:
        # accept ISO format with T
        if 'T' in dt_str:
            dt = datetime.fromisoformat(dt_str)
        else:
            # try to parse common variants
            dt = datetime.fromisoformat(dt_str)
    except Exception:
        # fallback: try common datetime patterns
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                dt = datetime.strptime(dt_str, fmt)
                break
            except Exception:
                dt = None
        if dt is None:
            return dt_str
    return dt.strftime('%d/%m/%Y - %H:%M')

app.jinja_env.globals['format_datetime'] = format_datetime_display


def format_availability_display(date_str, start_str, end_str):
    # date_str: YYYY-MM-DD, start_str/end_str: HH:MM
    try:
        d = date.fromisoformat(date_str)
        return f"{d.strftime('%d/%m/%Y')} - {start_str} to {end_str}"
    except Exception:
        return f"{date_str} {start_str}-{end_str}"

app.jinja_env.globals['format_availability'] = format_availability_display


# Carrega dados ao iniciar
load_data()

@app.route('/tabela_verdade')
def tabela_verdade():
    tabela = []
    total_normal = 0
    total_emergencia = 0
    for i in range(16):
        A = bool(i & 8)
        B = bool(i & 4)
        C = bool(i & 2)
        D = bool(i & 1)
        normal = (A and B and C) or (B and C and D)
        emergencia = C and (B or D)
        if normal:
            total_normal += 1
        if emergencia:
            total_emergencia += 1
        tabela.append({
            'A': 'V' if A else 'F',
            'B': 'V' if B else 'F',
            'C': 'V' if C else 'F',
            'D': 'V' if D else 'F',
            'normal': normal,
            'emergencia': emergencia
        })
    return render_template('tabela_verdade.html', tabela=tabela, total_normal=total_normal, total_emergencia=total_emergencia)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cadastrar', methods=['GET', 'POST'])
@login_required
@roles_required('secretaria')
def cadastrar():
    if request.method == 'POST':
        nome = request.form.get('nome')
        idade = request.form.get('idade')
        ddd = request.form.get('ddd')
        telefone_num = request.form.get('telefone_num')
        cpf = request.form.get('cpf', '')
        rg = request.form.get('rg', '')

        # Campos obrigatórios: nome, idade, ddd, telefone_num, cpf
        if not nome or not idade or not ddd or not telefone_num or not cpf:
            flash('Preencha todos os campos obrigatórios (incluindo CPF)!', 'error')
        else:
            # Validações simples de formato
            if not ddd.isdigit() or len(ddd) != 2:
                flash('DDD deve conter exatamente 2 dígitos.', 'error')
            elif not telefone_num.isdigit() or len(telefone_num) != 9:
                flash('Telefone deve conter exatamente 9 dígitos.', 'error')
            else:
                # converter idade e validar CPF/RG
                try:
                    idade_int = int(idade)
                except ValueError:
                    flash('Idade deve ser um número inteiro!', 'error')
                    return redirect(url_for('cadastrar'))

                # valida CPF (obrigatório)
                if not validate_cpf(cpf):
                    flash('CPF inválido. Verifique e tente novamente.', 'error')
                    return redirect(url_for('cadastrar'))

                # valida RG se informado
                if rg and not validate_rg(rg):
                    flash('RG com formato inválido. Digite apenas dígitos (7 a 9).', 'error')
                    return redirect(url_for('cadastrar'))

                telefone = f'({ddd}) {telefone_num}'
                paciente = {'nome': nome, 'idade': idade_int, 'telefone': telefone, 'cpf': only_digits(cpf), 'rg': only_digits(rg)}
                pacientes.append(paciente)
                save_data()
                flash('Paciente cadastrado com sucesso!', 'success')
                return redirect(url_for('cadastrar'))
    # Prepare patients for display: keep original index but sort alphabetically by name
    pacientes_display = []
    for i, p in enumerate(pacientes):
        pacientes_display.append({'idx': i, 'nome': p.get('nome', ''), 'idade': p.get('idade', ''), 'telefone': p.get('telefone', ''), 'cpf': p.get('cpf',''), 'rg': p.get('rg','')})
    pacientes_display = sorted(pacientes_display, key=lambda x: x['nome'].lower())
    return render_template('cadastrar.html', pacientes=pacientes_display)


@app.route('/paciente/editar/<int:idx>', methods=['GET', 'POST'])
@login_required
@roles_required('secretaria')
def editar_paciente(idx):
    if idx < 0 or idx >= len(pacientes):
        flash('Paciente não encontrado.', 'error')
        return redirect(url_for('cadastrar'))

    paciente = pacientes[idx]
    if request.method == 'POST':
        nome = request.form.get('nome')
        idade = request.form.get('idade')
        ddd = request.form.get('ddd')
        telefone_num = request.form.get('telefone_num')
        cpf = request.form.get('cpf', '')
        rg = request.form.get('rg', '')
        if not nome or not idade or not ddd or not telefone_num:
            flash('Preencha todos os campos!', 'error')
            return redirect(url_for('editar_paciente', idx=idx))
        if not ddd.isdigit() or len(ddd) != 2:
            flash('DDD deve conter exatamente 2 dígitos.', 'error')
            return redirect(url_for('editar_paciente', idx=idx))
        if not telefone_num.isdigit() or len(telefone_num) != 9:
            flash('Telefone deve conter exatamente 9 dígitos.', 'error')
            return redirect(url_for('editar_paciente', idx=idx))
        try:
            idade = int(idade)
            telefone = f'({ddd}) {telefone_num}'
            pacientes[idx] = {'nome': nome, 'idade': idade, 'telefone': telefone, 'cpf': only_digits(cpf), 'rg': only_digits(rg)}
            save_data()
            flash('Paciente atualizado com sucesso.', 'success')
            return redirect(url_for('cadastrar'))
        except ValueError:
            flash('Idade deve ser um número inteiro!', 'error')
            return redirect(url_for('editar_paciente', idx=idx))

    # GET -> show edit form
    # Reuse the cadastrar template but render a simple edit form here
    return render_template('editar_paciente.html', paciente=paciente, idx=idx)


@app.route('/paciente/apagar/<int:idx>', methods=['POST'])
@login_required
@roles_required('secretaria')
def apagar_paciente(idx):
    if idx < 0 or idx >= len(pacientes):
        flash('Paciente não encontrado.', 'error')
    else:
        removed = pacientes.pop(idx)
        save_data()
        flash(f"Paciente '{removed.get('nome','')}' apagado.", 'success')
    return redirect(url_for('cadastrar'))

@app.route('/estatisticas')
@login_required
@roles_required('secretaria', 'medico')
def estatisticas():
    total = len(pacientes)
    if total == 0:
        media = 0
        mais_novo = None
        mais_velho = None
    else:
        idades = [p['idade'] for p in pacientes]
        media = sum(idades) / total
        mais_novo = min(pacientes, key=lambda x: x['idade'])
        mais_velho = max(pacientes, key=lambda x: x['idade'])
    return render_template('estatisticas.html', total=total, media=media, mais_novo=mais_novo, mais_velho=mais_velho, pacientes=pacientes)

@app.route('/buscar', methods=['GET', 'POST'])
@login_required
@roles_required('secretaria', 'medico')
def buscar():
    resultado = None
    pacientes_list = None
    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()
        listar_todos = request.form.get('listar_todos')
        if nome:
            resultado = [p for p in pacientes if nome.lower() in p['nome'].lower()]
            resultado = sorted(resultado, key=lambda x: x['nome'].lower())
        else:
            resultado = []
        if listar_todos:
            # prepare full list sorted
            pacientes_list = sorted(pacientes, key=lambda x: x['nome'].lower())
    return render_template('buscar.html', resultado=resultado, pacientes_list=pacientes_list)

@app.route('/listar')
@login_required
@roles_required('secretaria', 'medico')
def listar():
    # build patient list including any agendamentos (not cancelled)
    pacientes_display = []
    for p in pacientes:
        nome = p.get('nome', '')
        ags = [a for a in agendamentos if a.get('paciente','').lower() == nome.lower() and a.get('status') != 'cancelado']
        datas = [a.get('data_hora') for a in ags]
        status = p.get('pagamento_em_dia', 'Em dia')
        # Se for boolean, converte para string padrão
        if status is True:
            status = 'Em dia'
        elif status is False:
            status = 'Atrasado'
        pacientes_display.append({'nome': nome, 'idade': p.get('idade',''), 'telefone': p.get('telefone',''), 'cpf': p.get('cpf',''), 'rg': p.get('rg',''), 'agendamentos': datas, 'pagamento_em_dia': status})
    # sort alphabetically
    pacientes_display = sorted(pacientes_display, key=lambda x: x['nome'].lower())
    return render_template('listar.html', pacientes=pacientes_display)

@app.route('/pagamentos', methods=['GET', 'POST'])
@login_required
@roles_required('secretaria', 'medico')
def pagamentos():
    # Oculta para médico
    if session.get('role') == 'medico':
        flash('Acesso negado para médicos à tela de pagamentos.', 'error')
        return redirect(url_for('index'))
    busca_nome = request.args.get('busca', '').strip().lower()
    busca_doc = request.args.get('busca_doc', '').strip()
    busca_status = request.args.get('busca_status', '').strip()
    pacientes_exibir = []
    for p in pacientes:
        nome = p.get('nome', '')
        cpf = p.get('cpf', '')
        rg = p.get('rg', '')
        status = p.get('pagamento_em_dia', 'Em dia')
        if status is True:
            status = 'Em dia'
        elif status is False:
            status = 'Atrasado'
        # Filtro por nome
        if busca_nome and busca_nome not in nome.lower():
            continue
        # Filtro por CPF/RG
        if busca_doc and busca_doc not in cpf and busca_doc not in rg:
            continue
        # Filtro por status
        if busca_status and busca_status != status:
            continue
        pacientes_exibir.append({'nome': nome, 'cpf': cpf, 'rg': rg, 'pagamento_em_dia': status})
    return render_template('pagamentos.html', pacientes=pacientes_exibir, busca_nome=busca_nome, busca_doc=busca_doc, busca_status=busca_status)

@app.route('/controle', methods=['GET', 'POST'])
def controle():
    # Rota antiga 'controle' agora redireciona para agendamento
    return redirect(url_for('agendamento'))


@app.route('/agendamento', methods=['GET', 'POST'])
@login_required
@roles_required('secretaria', 'medico')
def agendamento():
    # Exibe formulário para criar agendamentos e lista existentes
    mensagem = ''
    if request.method == 'POST':
        # Criar novo agendamento
        if 'agendar' in request.form:
            paciente_nome = request.form.get('paciente')
            data_hora = request.form.get('data_hora')
            if not paciente_nome or not data_hora:
                mensagem = 'Selecione paciente e informe data/hora.'
            else:
                # Verifica se paciente está cadastrado
                exists = any(p['nome'].lower() == paciente_nome.lower() for p in pacientes)
                if not exists:
                    mensagem = 'Paciente não cadastrado. Cadastre antes de agendar.'
                else:
                    # Verificar conflitos considerando margem de 30 minutos (antes/depois)
                    try:
                        new_dt = datetime.fromisoformat(data_hora)
                    except Exception:
                        mensagem = 'Formato de data/hora inválido.'
                    else:
                        conflict = None
                        indisponivel = False
                        for d in disponibilidades:
                            try:
                                disp_data = date.fromisoformat(d.get('data'))
                                disp_inicio = datetime.strptime(d.get('inicio'), '%H:%M').time()
                                disp_fim = datetime.strptime(d.get('fim'), '%H:%M').time()
                            except Exception:
                                continue
                            if new_dt.date() == disp_data:
                                if disp_inicio <= new_dt.time() <= disp_fim:
                                    indisponivel = True
                                    break
                        if indisponivel:
                            mensagem = 'Indisponibilidade de médico neste horário. Não é possível agendar.'
                        else:
                            for a in agendamentos:
                                if a.get('status') == 'cancelado':
                                    continue
                                try:
                                    existing_dt = datetime.fromisoformat(a.get('data_hora'))
                                except Exception:
                                    continue
                                diff = abs((existing_dt - new_dt).total_seconds())
                                if diff < 30 * 60:  # menos de 30 minutos de diferença
                                    conflict = a
                                    break
                            if conflict:
                                mensagem = f"Conflito: já existe agendamento para {conflict.get('paciente')} em {conflict.get('data_hora')} (dentro de 30 minutos)."
                            else:
                                next_id = max([a.get('id', 0) for a in agendamentos], default=0) + 1
                                ag = {'id': next_id, 'paciente': paciente_nome, 'data_hora': data_hora, 'status': 'agendado'}
                                agendamentos.append(ag)
                                save_data()
                                mensagem = 'Agendamento criado.'
        # Confirmar agendamento
        elif 'confirmar' in request.form:
            aid = int(request.form.get('confirmar'))
            for a in agendamentos:
                if a.get('id') == aid:
                    a['status'] = 'confirmado'
                    save_data()
                    mensagem = f"Agendamento {aid} confirmado."
                    break
        # Cancelar agendamento
        elif 'cancelar' in request.form:
            aid = int(request.form.get('cancelar'))
            for a in agendamentos:
                if a.get('id') == aid:
                    a['status'] = 'cancelado'
                    save_data()
                    mensagem = f"Agendamento {aid} cancelado."
                    break
        # Apagar agendamento (remover completamente)
        elif 'apagar' in request.form:
            aid = int(request.form.get('apagar'))
            removed = None
            for i, a in enumerate(agendamentos):
                if a.get('id') == aid:
                    removed = agendamentos.pop(i)
                    save_data()
                    mensagem = f"Agendamento {aid} apagado." 
                    break

    # Envia lista de pacientes (para o select) e agendamentos
    pacientes_nomes = [p['nome'] for p in pacientes]
    # Ordena agendamentos por data_hora usando parsing para garantir ordem correta
    def sort_key(a):
        dh = a.get('data_hora')
        try:
            return datetime.fromisoformat(dh)
        except Exception:
            return datetime.max
    ag_sorted = sorted(agendamentos, key=sort_key)
    # Support filtering by day (GET param 'dia' as YYYY-MM-DD)
    filter_day = None
    dia = request.args.get('dia')
    if dia:
        try:
            date_obj = date.fromisoformat(dia)
            filter_day = dia
            filtered = []
            for a in ag_sorted:
                try:
                    adt = datetime.fromisoformat(a.get('data_hora'))
                    if adt.date() == date_obj:
                        filtered.append(a)
                except Exception:
                    continue
            ag_sorted = filtered
        except Exception:
            pass

    return render_template('agendamento.html', pacientes=pacientes_nomes, agendamentos=ag_sorted, mensagem=mensagem, filter_day=filter_day)


# --- Authentication routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username') or ''
        password = request.form.get('password') or ''
        username_norm = username.strip().lower()
        password = password.strip()
        user = USERS.get(username_norm)
        if user and user.get('password') == password:
            session['username'] = username_norm
            session['role'] = user.get('role')
            flash('Login realizado com sucesso.', 'success')
            return redirect(url_for('index'))
        else:
            error = 'Usuário ou senha inválidos.'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# --- Prescriptions (receitas) ---
@app.route('/receita/novo', methods=['GET', 'POST'])
@login_required
@roles_required('medico')
def nova_receita():
    if request.method == 'POST':
        paciente_idx = request.form.get('paciente')
        conteudo = request.form.get('conteudo', '').strip()
        if paciente_idx is None or paciente_idx == '':
            return render_template('receita.html', pacientes=pacientes, error='Selecione um paciente.')
        try:
            paciente_idx = int(paciente_idx)
            paciente = pacientes[paciente_idx]
        except Exception:
            paciente = {'nome': 'Desconhecido'}

        receita = {
            'paciente': paciente.get('nome'),
            'conteudo': conteudo,
            'medico': session.get('username'),
            'data': datetime.now().isoformat()
        }
        receitas.append(receita)
        save_data()
        return redirect(url_for('imprimir_receita', idx=len(receitas)-1))

    return render_template('receita.html', pacientes=pacientes)


@app.route('/receitas')
@login_required
@roles_required('medico', 'secretaria')
def listar_receitas():
    return render_template('receitas.html', receitas=receitas)


@app.route('/receita/print/<int:idx>')
@login_required
@roles_required('medico', 'secretaria')
def imprimir_receita(idx):
    if idx < 0 or idx >= len(receitas):
        return 'Receita não encontrada', 404
    receita = receitas[idx]
    return render_template('receita_print.html', receita=receita)

# Rota para apagar receita
@app.route('/receita/apagar/<int:idx>', methods=['POST'])
@login_required
@roles_required('medico', 'secretaria')
def apagar_receita(idx):
    if idx < 0 or idx >= len(receitas):
        flash('Receita não encontrada.', 'error')
        return redirect(url_for('listar_receitas'))
    receitas.pop(idx)
    save_data()
    flash('Receita apagada com sucesso.', 'success')
    return redirect(url_for('listar_receitas'))

# Rota para configurações de usuário
@app.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def configuracoes():


    mensagem = ''
    erro = ''
    if request.method == 'POST':
        senha_atual = request.form.get('senha_atual')
        novo_username = request.form.get('novo_username')
        nova_senha = request.form.get('nova_senha')
        confirma_senha = request.form.get('confirma_senha')
        user = USERS.get(session.get('username'))
        if not user or user.get('password') != senha_atual:
            erro = 'Senha atual incorreta.'
        elif nova_senha and nova_senha != confirma_senha:
            erro = 'Nova senha e confirmação não conferem.'
        else:
            # Troca nome de usuário
            nome_antigo = session.get('username')
            nome_novo = novo_username.strip().lower() if novo_username else nome_antigo
            if nome_novo != nome_antigo:
                if nome_novo in USERS:
                    erro = 'Nome de usuário já existe.'
                else:
                    USERS[nome_novo] = USERS.pop(nome_antigo)
                    session['username'] = nome_novo
                    mensagem = 'Nome de usuário alterado com sucesso.'
            # Troca senha
            if nova_senha and not erro:
                USERS[session.get('username')]['password'] = nova_senha
                mensagem += ' Senha alterada com sucesso.'
            # Persistir alterações em arquivo
            try:
                with open('users.json', 'w', encoding='utf-8') as f:
                    json.dump(USERS, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        if erro:
            flash(erro, 'error')
        elif mensagem:
            flash(mensagem, 'success')
    return render_template('configuracoes.html')

# Rota para diagrama de casos de uso
@app.route('/casos_uso', methods=['GET', 'POST'])
def casos_uso():

    # ...existing code...
    # ...existing code...
    # Página agora lida com indisponibilidades do médico. Secretária visualiza, médico pode adicionar/remover.
    message = ''
    if request.method == 'POST':
        # Apenas médicos podem criar ou remover indisponibilidades
        if 'username' not in session or session.get('role') != 'medico':
            flash('Apenas médico pode alterar indisponibilidades.', 'error')
            return redirect(url_for('casos_uso'))

        # Criar nova indisponibilidade
        if 'criar_disp' in request.form:
            data_disp = request.form.get('data_disp')
            inicio = request.form.get('inicio')
            fim = request.form.get('fim')
            if not data_disp or not inicio or not fim:
                flash('Preencha data, início e fim da indisponibilidade.', 'error')
            else:
                next_id = max([d.get('id', 0) for d in disponibilidades], default=0) + 1
                disponibilidades.append({'id': next_id, 'data': data_disp, 'inicio': inicio, 'fim': fim, 'medico': session.get('username')})
                save_data()
                flash('Indisponibilidade adicionada.', 'success')
        elif 'apagar_disp' in request.form:
            did = int(request.form.get('apagar_disp'))
            for i, d in enumerate(disponibilidades):
                if d.get('id') == did:
                    disponibilidades.pop(i)
                    save_data()
                    flash('Indisponibilidade removida.', 'success')
                    break

    # Exibir todas as indisponibilidades ordenadas por data
    def dkey(x):
        try:
            return date.fromisoformat(x.get('data'))
        except Exception:
            return date.max

    disp_sorted = sorted(disponibilidades, key=dkey)
    return render_template('casos_uso.html', disponibilidades=disp_sorted)

@app.route('/evolucao', methods=['GET', 'POST'])
@login_required
@roles_required('medico')
def evolucao():
    # Inicializa campo de evolução se não existir
    for p in pacientes:
        if 'evolucao' not in p:
            p['evolucao'] = []
    paciente_idx = request.args.get('paciente')
    evolucoes = []
    paciente = None
    msg = ''
    if paciente_idx is not None and paciente_idx != '':
        try:
            paciente_idx = int(paciente_idx)
            paciente = pacientes[paciente_idx]
            evolucoes = paciente.get('evolucao', [])
        except Exception:
            paciente = None
            evolucoes = []
    if request.method == 'POST' and paciente:
        # Adicionar nova situação
        if 'adicionar' in request.form:
            nova_situacao = request.form.get('nova_situacao', '').strip()
            if nova_situacao:
                evolucoes.append(nova_situacao)
                paciente['evolucao'] = evolucoes
                save_data()
                msg = 'Situação salva.'
        # Editar situação
        elif 'editar' in request.form:
            edit_idx = int(request.form.get('edit_idx', -1))
            if 0 <= edit_idx < len(evolucoes):
                # Exibe campo para edição
                msg = f'Edite a situação abaixo:'
                return render_template('evolucao.html', pacientes=pacientes, paciente=paciente, evolucoes=evolucoes, paciente_idx=paciente_idx, edit_idx=edit_idx, edit_text=evolucoes[edit_idx], msg=msg)
        # Salvar edição
        elif 'salvar_edicao' in request.form:
            edit_idx = int(request.form.get('edit_idx', -1))
            edit_text = request.form.get('edit_text', '').strip()
            if 0 <= edit_idx < len(evolucoes) and edit_text:
                evolucoes[edit_idx] = edit_text
                paciente['evolucao'] = evolucoes
                save_data()
                msg = 'Situação editada.'
        # Apagar situação
        elif 'apagar' in request.form:
            edit_idx = int(request.form.get('edit_idx', -1))
            if 0 <= edit_idx < len(evolucoes):
                evolucoes.pop(edit_idx)
                paciente['evolucao'] = evolucoes
                save_data()
                msg = 'Situação apagada.'
    return render_template('evolucao.html', pacientes=pacientes, paciente=paciente, evolucoes=evolucoes, paciente_idx=paciente_idx, msg=msg)

if __name__ == '__main__':
    @app.route('/sobre')
    @login_required
    def sobre():
        return render_template('sobre.html')
    app.run(host='0.0.0.0', port=5000, debug=True)
