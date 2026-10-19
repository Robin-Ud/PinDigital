# PinDigital

Pinentry do `rbw` que destrava o Bitwarden com a digital. Super+B (rofi-rbw) →
encosta o dedo → pronto. Puro Python, zero deps.

## Como funciona

- O `rbw-agent` chama este pinentry quando precisa da senha mestra.
- O dedo é conferido com `fprintd-verify`, direto no fprintd. **Não passa pelo PAM**, então
  continua funcionando com a digital fora do sistema (`authselect` sem `with-fingerprint`).
- Bateu → devolve a senha mestra guardada no gnome-keyring (que destrava no login).
- Cai no `pinentry-gnome3` normal quando: o dedo não bate (3 tentativas), não tem
  senha salva, a senha salva está errada (o rbw manda `SETERROR`) ou o pedido não é a
  senha mestra (2FA etc.).

## Instalar

```
rbw config set pinentry ~/deving/desktop/PinDigital/pindigital.sh
rbw stop-agent
./pindigital.sh --salvar      # num terminal de verdade: pede a senha mestra 2x
rbw unlock                    # testa: deve pedir o dedo
```

Trocou a senha mestra? `./pindigital.sh --salvar` de novo. Tirar do keyring: `--apagar`.
Desligar tudo: `rbw config set pinentry pinentry-gnome3`.

## Arquivos

- `pindigital.py` — tudo
- `configs.json` — caminhos dos programas e nº de tentativas do dedo
- `pindigital_test.sh` — teste com programas falsos em /tmp (não toca keyring nem leitor)

## Segurança

A senha mestra fica no gnome-keyring, protegida pela senha de login. É o mesmo
esquema do app desktop do Bitwarden: o dedo só autoriza a liberar o que já está guardado.
