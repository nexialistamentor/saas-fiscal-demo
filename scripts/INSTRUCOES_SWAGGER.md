# Fluxo de teste no Swagger (ordem de execução)

## Pré-requisitos

1. **Subir a API:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

2. **Criar planos (primeira vez):**
   ```bash
   python scripts/preparar_testes.py
   ```

## Swagger UI

Acesse: **http://localhost:8000/swagger**

---

## Ordem de execução

### 1. Criar usuário

- Abra **POST /auth/register**
- Clique em **Try it out**
- Use:
  ```json
  {
    "email": "teste@empresa.com",
    "password": "senha123"
  }
  ```
- Clique em **Execute**

Se o usuário já existir (400 "Email já cadastrado"), ignore e siga para o login.

---

### 2. Fazer login

- Abra **POST /auth/login**
- Clique em **Try it out**
- Preencha:
  - **username:** teste@empresa.com
  - **password:** senha123
- Clique em **Execute**

A resposta deve trazer:
```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

Copie o valor de `access_token`.

---

### 3. Autorizar a API

- No topo da página, clique em **Authorize**
- Cole o token no formato: `Bearer SEU_TOKEN_AQUI`  
  (substitua `SEU_TOKEN_AQUI` pelo access_token do passo 2)
- Clique em **Authorize**
- Feche o modal

---

### 4. Testar endpoint protegido

- Abra **POST /upload-xml**
- Clique em **Try it out**
- No campo **file**, envie um arquivo XML de NF-e (ex.: `app/xmls_testes/xml_icms_st_teste.xml`)
- Clique em **Execute**

A resposta deve trazer algo como:
```json
{
  "documento_id": 1
}
```

---

## Script automatizado

Para executar todos os passos de uma vez:

```bash
python scripts/testar_api_swagger.py
```

(O script faz register, login e upload-xml automaticamente.)
