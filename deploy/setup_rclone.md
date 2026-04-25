# Configuração do rclone com OneDrive na VPS

> Execute estes passos **uma única vez** na VPS. Após configurado, o backup roda automaticamente.

## Pré-requisitos

- VPS com acesso à internet
- Conta OneDrive (pessoal ou Microsoft 365)
- Acesso SSH à VPS

---

## Passo 1 — Instalar o rclone na VPS

```bash
curl https://rclone.org/install.sh | sudo bash
rclone version   # Verifica instalação
```

---

## Passo 2 — Configurar o remote do OneDrive

O rclone precisa de uma autenticação OAuth com o OneDrive.
Como a VPS não tem navegador, usamos **autenticação remota via túnel**.

### 2.1 — Iniciar a configuração na VPS

```bash
rclone config
```

Responda às perguntas:
```
n) New remote
name> onedrive
Storage> onedrive           # (escolha o número correspondente a "Microsoft OneDrive")
client_id>                  # deixe em branco (Enter)
client_secret>              # deixe em branco (Enter)
region>                     # 1 (Microsoft Cloud Global)
Edit advanced config? n
Use auto config? n          # ← IMPORTANTE: escolha "n" pois a VPS não tem browser
```

A VPS exibirá uma URL longa. **Copie essa URL.**

### 2.2 — Autenticar no seu computador local

No seu computador Windows (com browser disponível):

```powershell
# Instale rclone localmente se ainda não tiver:
winget install Rclone.Rclone

# Execute o authorize passando a URL copiada da VPS
rclone authorize "onedrive"
```

O browser abrirá para login Microsoft. Após autenticar, o terminal exibirá um **token JSON**.
Copie o token inteiro (começa com `{"access_token":...}`).

### 2.3 — Cole o token na VPS

De volta ao terminal da VPS, cole o token quando solicitado.

Continue a configuração:
```
config_type> onedrive       # 1 (OneDrive Personal or Business)
drive_id>                   # pressione Enter para selecionar o drive padrão
root_folder_id>             # pressione Enter
Keep this "onedrive" remote? y
q) Quit config
```

---

## Passo 3 — Verificar a configuração

```bash
# Testa se o rclone consegue listar o OneDrive
rclone ls onedrive:

# Cria a pasta de backups no OneDrive
rclone mkdir onedrive:maisevplus_backups

# Confirma que a pasta foi criada
rclone ls onedrive:maisevplus_backups
```

---

## Passo 4 — Adicionar variáveis ao .env da VPS

Adicione ao arquivo `/root/maisevplus_webscraping/.env`:

```bash
# --- Backup OneDrive ---
RCLONE_REMOTE=onedrive
BACKUP_ONEDRIVE_PATH=maisevplus_backups
BACKUP_LOCAL_RETENTION_DAYS=2
BACKUP_ONEDRIVE_RETENTION_COUNT=5
```

---

## Passo 5 — Testar o script de backup manualmente

```bash
cd /root/maisevplus_webscraping
bash scripts/backup_db.sh
```

Deve produzir saída similar a:
```
INFO: Iniciando pg_dump de 'maisevplus_db' em 127.0.0.1:5432...
INFO: Backup criado com sucesso. SIZE: 42M → ...
INFO: Enviando para onedrive:maisevplus_backups/...
INFO: Upload concluído.
INFO: ✅ Backup finalizado com sucesso. SIZE: 42M
```

---

## Passo 6 — Confirmar no OneDrive

Acesse [onedrive.live.com](https://onedrive.live.com) e verifique a pasta `maisevplus_backups`.

---

## Troubleshooting

| Problema | Solução |
|---|---|
| `rclone: command not found` | Reinstalar: `curl https://rclone.org/install.sh \| sudo bash` |
| `Failed to create file system: didn't find section in config` | Rodar `rclone config` novamente e reautenticar |
| `pg_dump: command not found` | Instalar: `sudo apt install postgresql-client` |
| Token expirado (após 1 ano) | Rodar `rclone config reconnect onedrive:` |
