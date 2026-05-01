let protocoloAtual = null;
let dadosUsuario = {};
let atendimentoEncerrado = false;
let timerInatividade = null;
let avisoInatividade = 0;

function resetarTimerInatividade() {
    clearTimeout(timerInatividade);
    avisoInatividade = 0;

    // 5 minutos sem resposta — avisa o usuário
    timerInatividade = setTimeout(() => {
        if (!atendimentoEncerrado) {
            avisoInatividade++;
            if (avisoInatividade === 1) {
                appendMsgAnimada("Ainda está aí? Se o problema foi resolvido, pode me dizer 'obrigado' ou 'resolveu' para encerrar. Se precisar de mais ajuda, pode continuar.", "bot");
                resetarTimerInatividade();
            } else if (avisoInatividade === 2) {
                appendMsgAnimada("Não detectei resposta. Vou encerrar esse atendimento automaticamente em 1 minuto caso não haja retorno.", "bot");
                resetarTimerInatividade();
            } else {
                appendMsgAnimada("Atendimento encerrado por inatividade. Se precisar de ajuda, abra uma nova solicitação.", "bot");
                mostrarEncerrado("ENCERRADO");
                fetch('https://helpbot-vcul.onrender.com/chamados/verificar-inatividade', { method: 'POST' });
            }
        }
    }, 5 * 60 * 1000); // 5 minutos
}

function iniciarAtendimento() {
    const nome = document.getElementById('nome').value.trim();
    const tel = document.getElementById('telefone').value.trim();
    const email = document.getElementById('email').value.trim();

    const regexNome = /^[a-zA-ZÀ-ÿ\s]{3,}$/;
    const digitos = tel.replace(/\D/g, '');

    if (!regexNome.test(nome)) {
        alert("Nome inválido. Use apenas letras e espaços, mínimo 3 caracteres.");
        return;
    }
    if (digitos.length < 10) {
        alert("Telefone inválido. Use o formato (XX) 9 XXXX-XXXX.");
        return;
    }
    if (!email.includes('@') || !email.includes('.')) {
        alert("E-mail inválido.");
        return;
    }

    dadosUsuario = { nome, tel, email };

    const login = document.getElementById('login-screen');
    login.classList.add('fade-out');

    setTimeout(() => {
        login.style.display = 'none';
        const chat = document.getElementById('chat-container');
        chat.style.display = 'flex';
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                chat.classList.add('fade-in');
            });
        });
        appendMsgAnimada("Olá, " + nome + "! 👋 Sou o HelpBot, seu assistente de suporte técnico. Como posso te ajudar hoje?", "bot");
    }, 500);
    resetarTimerInatividade();
}

async function enviarMensagem() {
    if (atendimentoEncerrado) return;

    const input = document.getElementById('user-input');
    const texto = input.value.trim();
    if (!texto) return;

    appendMsg(texto, "user");
    input.value = "";

    // Indicador de digitação
    const typing = mostrarTyping();

    try {
        const response = await fetch('https://helpbot-vcul.onrender.com/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                texto,
                protocolo: protocoloAtual,
                dados_pre_coleta: `NOME: ${dadosUsuario.nome} | TEL: ${dadosUsuario.tel} | EMAIL: ${dadosUsuario.email}`
            })
        });

        const data = await response.json();
        protocoloAtual = data.protocolo;

        document.getElementById('prot-val').innerText = data.protocolo;
        document.getElementById('stat-val').innerText = data.status;

        typing.remove();
        await appendMsgAnimada(data.resposta, "bot");

        if (data.status === "ENCERRADO" || data.status === "NÃO SOLUCIONADO") {
            setTimeout(() => mostrarEncerrado(data.status), 800);
        }

    } catch (e) {
        typing.remove();
        appendMsgAnimada("Erro de conexão com o servidor. Tente novamente.", "bot");
    }
    resetarTimerInatividade();
}

function mostrarTyping() {
    const win = document.getElementById('chat-window');
    const div = document.createElement('div');
    div.className = 'typing-indicator';
    div.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
    win.appendChild(div);
    win.scrollTop = win.scrollHeight;
    return div;
}

function appendMsg(txt, side) {
    const win = document.getElementById('chat-window');
    const div = document.createElement('div');
    div.className = `msg ${side}`;
    div.innerText = txt;
    win.appendChild(div);
    win.scrollTop = win.scrollHeight;
    return div;
}

async function appendMsgAnimada(txt, side) {
    const win = document.getElementById('chat-window');
    const div = document.createElement('div');
    div.className = `msg ${side}`;
    win.appendChild(div);
    win.scrollTop = win.scrollHeight;

    if (side === 'bot') {
        // Usa span interno pra preservar espaços corretamente
        const span = document.createElement('span');
        span.style.whiteSpace = 'pre-wrap';
        div.appendChild(span);

        for (let i = 0; i < txt.length; i++) {
            span.textContent += txt[i];
            win.scrollTop = win.scrollHeight;
            await sleep(12);
        }
    } else {
        div.innerText = txt;
    }

    return div;
}

function mostrarEncerrado(status) {
    atendimentoEncerrado = true;

    // Some a área de input
    document.querySelector('.input-area').style.display = 'none';

    // Mostra tela de encerramento
    const enc = document.getElementById('encerrado-screen');
    enc.style.display = 'flex';

    if (status === 'ENCERRADO') {
        document.getElementById('enc-icon').className = 'encerrado-icon icon-ok';
        document.getElementById('enc-icon').innerText = '✅';
        document.getElementById('enc-titulo').innerText = 'Atendimento encerrado!';
        document.getElementById('enc-msg').innerText =
            'Seu chamado foi registrado com o protocolo #' + protocoloAtual +
            '. Esperamos ter ajudado! Se precisar de mais suporte, abra uma nova solicitação.';
    } else {
        document.getElementById('enc-icon').className = 'encerrado-icon icon-tecnico';
        document.getElementById('enc-icon').innerText = '🔧';
        document.getElementById('enc-titulo').innerText = 'Técnico a caminho!';
        document.getElementById('enc-msg').innerText =
            'Seu chamado #' + protocoloAtual +
            ' foi registrado e um técnico será enviado ao seu local. Aguarde o contato da equipe.';
    }

    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            enc.classList.add('fade-in');
        });
    });
}

function reiniciarChat() {
    // Reset variáveis
    clearTimeout(timerInatividade);
    avisoInatividade = 0;
    atendimentoEncerrado = false;
    protocoloAtual = null;
    dadosUsuario = {};

    // Limpa campos de login
    document.getElementById('nome').value = '';
    document.getElementById('telefone').value = '';
    document.getElementById('email').value = '';

    // Reset chat
    document.getElementById('chat-window').innerHTML = '';
    document.getElementById('prot-val').innerText = '—';
    document.getElementById('stat-val').innerText = '—';
    document.querySelector('.input-area').style.display = 'flex';

    // Esconde encerrado
    const enc = document.getElementById('encerrado-screen');
    enc.classList.remove('fade-in');
    enc.style.display = 'none';

    // Fade out chat
    const chat = document.getElementById('chat-container');
    chat.classList.remove('fade-in');

    setTimeout(() => {
        chat.style.display = 'none';

        // Mostra login com fade in
        const login = document.getElementById('login-screen');
        login.style.display = 'block';
        login.classList.remove('fade-out');
    }, 500);
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Enter para enviar
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('user-input').addEventListener('keydown', e => {
        if (e.key === 'Enter') enviarMensagem();
    });
});