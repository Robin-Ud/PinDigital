#!/usr/bin/env python3
"""PinDigital — pinentry do rbw que destrava com a digital.

O rbw-agent fala o protocolo Assuan com o pinentry pelo stdin/stdout. Quando
ele pede a senha mestra, a gente confere o dedo com fprintd-verify (direto no
fprintd, não passa pelo PAM) e devolve a senha guardada no gnome-keyring.
Qualquer outra coisa (2FA, senha errada, dedo que não bateu, senha não salva)
vai pro pinentry de verdade, repassando os comandos que o rbw já mandou.

Uso:
  pindigital.py            modo pinentry (é o que o rbw chama)
  pindigital.py --salvar   guarda a senha mestra no keyring
  pindigital.py --apagar   tira a senha do keyring
"""
import getpass
import json
import os
import subprocess
import sys

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.environ.get("PINDIGITAL_CONFIG", os.path.join(DATA_DIR, "configs.json"))
# atributos do item no keyring
ATTRS = ["app", "pindigital", "item", "rbw-senha-mestra"]


def carrega_config():
    with open(CONFIG) as f:
        return json.load(f)


def garante_dbus():
    # o rbw-agent pode rodar sem DBUS_SESSION_BUS_ADDRESS; o secret-tool precisa dele
    if "DBUS_SESSION_BUS_ADDRESS" not in os.environ:
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"


# --- Assuan: % escapa %, CR e LF ---

def desescapa(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "%" and len(s[i + 1:i + 3]) == 2:
            try:
                out.append(chr(int(s[i + 1:i + 3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        out.append(s[i])
        i += 1
    return "".join(out)


def escapa(s):
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def responde(linha):
    sys.stdout.write(linha + "\n")
    sys.stdout.flush()


# --- digital e keyring ---

def senha_guardada(cfg):
    r = subprocess.run([cfg["secret_tool"], "lookup", *ATTRS],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 and r.stdout else None


def avisa(cfg, msg):
    try:
        subprocess.run([cfg["notify_send"], "-a", "rbw", "-t", "5000", "Bitwarden", msg],
                       capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def dedo_confere(cfg):
    for _ in range(cfg.get("tentativas_dedo", 3)):
        avisa(cfg, "Encoste o dedo no leitor")
        try:
            r = subprocess.run([cfg["fprintd_verify"]], capture_output=True, text=True)
        except OSError:
            return False
        if r.returncode == 0 and "verify-match" in r.stdout:
            return True
        # leitor ocupado/sem digital cadastrada não adianta repetir
        if "verify-no-match" not in r.stdout and "verify-retry" not in r.stdout:
            return False
    return False


# --- repasse pro pinentry de verdade ---

class PinentryReal:
    def __init__(self, cfg, historico):
        self.p = subprocess.Popen([cfg["pinentry_real"]], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, bufsize=1)
        self._le_ate_ok()  # saudação
        for cmd in historico:
            self.manda(cmd)

    def _le_ate_ok(self):
        linhas = []
        while True:
            l = self.p.stdout.readline()
            if not l:
                return linhas + ["ERR 83886179 pinentry real fechou"]
            l = l.rstrip("\n")
            linhas.append(l)
            if l.startswith("OK") or l.startswith("ERR"):
                return linhas

    def manda(self, cmd):
        self.p.stdin.write(cmd + "\n")
        self.p.stdin.flush()
        return self._le_ate_ok()

    def fecha(self):
        try:
            self.p.stdin.write("BYE\n")
            self.p.stdin.close()
        except OSError:
            pass
        self.p.wait(timeout=5)


def modo_pinentry():
    cfg = carrega_config()
    garante_dbus()
    historico = []      # tudo que o rbw configurou, pra repassar se cair no real
    prompt, erro = "", False
    real = None
    responde("OK PinDigital")
    for linha in sys.stdin:
        linha = linha.rstrip("\n")
        cmd, _, arg = linha.partition(" ")
        cmd = cmd.upper()
        if cmd == "BYE":
            responde("OK")
            break
        if cmd != "GETPIN":
            if cmd == "SETPROMPT":
                prompt = desescapa(arg)
            elif cmd == "SETERROR" and arg:
                erro = True  # senha anterior falhou: não insiste na guardada
            historico.append(linha)
            if real:
                for l in real.manda(linha):
                    responde(l)
            else:
                responde("OK")
            continue

        # GETPIN
        if not real and not erro and cfg["prompt_senha_mestra"] in prompt:
            senha = senha_guardada(cfg)
            if senha and dedo_confere(cfg):
                responde("D " + escapa(senha))
                responde("OK")
                continue
        if not real:
            real = PinentryReal(cfg, historico)
        for l in real.manda("GETPIN"):
            responde(l)
    if real:
        real.fecha()


def salvar():
    garante_dbus()
    cfg = carrega_config()
    s1 = getpass.getpass("Senha mestra do Bitwarden: ")
    s2 = getpass.getpass("De novo: ")
    if not s1 or s1 != s2:
        sys.exit("Não bateu, nada salvo.")
    r = subprocess.run([cfg["secret_tool"], "store", "--label=rbw (PinDigital)", *ATTRS],
                       input=s1, text=True)
    if r.returncode:
        sys.exit("secret-tool falhou.")
    print("Salva. Teste com: rbw lock && rbw unlock")


def apagar():
    garante_dbus()
    cfg = carrega_config()
    subprocess.run([cfg["secret_tool"], "clear", *ATTRS])
    print("Removida do keyring.")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--salvar":
        salvar()
    elif arg == "--apagar":
        apagar()
    else:
        # pinentry recebe opções tipo --display, --ttyname: ignora
        modo_pinentry()
