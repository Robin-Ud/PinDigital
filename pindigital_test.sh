#!/bin/bash
# Teste isolado: secret-tool, fprintd-verify, notify-send e pinentry falsos em /tmp.
# Não toca no keyring nem no leitor de verdade.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
T="$(mktemp -d /tmp/pindigital_test.XXXX)"
trap 'rm -rf "$T"' EXIT

cat > "$T/secret-tool" <<'X'
#!/bin/bash
[ -f "$T_DIR/senha" ] && printf '%s' "$(cat "$T_DIR/senha")" || exit 1
X
cat > "$T/fprintd-verify" <<'X'
#!/bin/bash
echo "Verify result: $(cat "$T_DIR/dedo") (done)"
[ "$(cat "$T_DIR/dedo")" = verify-match ]
X
printf '#!/bin/bash\nexit 0\n' > "$T/notify-send"
cat > "$T/pinentry" <<'X'
#!/bin/bash
echo "OK real"
while read -r l; do
  case "$l" in
    GETPIN) echo "D digitada"; echo OK ;;
    BYE) echo OK; exit 0 ;;
    *) echo OK ;;
  esac
done
X
chmod +x "$T"/*
cat > "$T/configs.json" <<X
{"pinentry_real": "$T/pinentry", "fprintd_verify": "$T/fprintd-verify",
 "secret_tool": "$T/secret-tool", "notify_send": "$T/notify-send",
 "tentativas_dedo": 2, "prompt_senha_mestra": "Master Password"}
X
export T_DIR="$T" PINDIGITAL_CONFIG="$T/configs.json"

falhas=0
roda() {  # nome, esperado, comandos...
  local nome="$1" esperado="$2"; shift 2
  local saida; saida="$(printf '%s\n' "$@" | python3 "$DIR/pindigital.py" | grep '^D ')"
  if [ "$saida" = "$esperado" ]; then echo "ok   $nome"; else echo "FALHA $nome: '$saida' != '$esperado'"; falhas=$((falhas+1)); fi
}

printf 'a%%b\nc' > "$T/senha"; echo verify-match > "$T/dedo"
roda "dedo bate -> senha guardada (escapada)" "D a%25b%0Ac" "SETPROMPT Master Password" GETPIN BYE
echo verify-no-match > "$T/dedo"
roda "dedo não bate -> pinentry real" "D digitada" "SETPROMPT Master Password" GETPIN BYE
echo verify-match > "$T/dedo"
roda "SETERROR -> pinentry real" "D digitada" "SETPROMPT Master Password" "SETERROR Senha errada" GETPIN BYE
roda "outro prompt (2FA) -> pinentry real" "D digitada" "SETPROMPT Authenticator App" GETPIN BYE
rm "$T/senha"
roda "sem senha guardada -> pinentry real" "D digitada" "SETPROMPT Master Password" GETPIN BYE

[ $falhas = 0 ] && echo "tudo certo" || { echo "$falhas falha(s)"; exit 1; }
