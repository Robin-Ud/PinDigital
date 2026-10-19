# PinDigital

Pinentry (protocolo Assuan) pro rbw: confere o dedo com fprintd-verify e devolve a senha mestra do
gnome-keyring (secret-tool, attrs app=pindigital item=rbw-senha-mestra); senão repassa tudo
pro pinentry real (configs.json). Ligado via `rbw config set pinentry .../pindigital.sh`.

- Nunca rodar fprintd-verify/secret-tool de verdade em teste: use `./pindigital_test.sh`
  (PINDIGITAL_CONFIG aponta pra fakes em /tmp).
- A digital foi tirada do PAM de propósito (só Bitwarden usa); não reativar.
