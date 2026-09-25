# Consulta de CEP para leads do Odoo

Serviço para Railway. O Odoo envia um lead ao endpoint `POST /consultar-cep/<WEBHOOK_TOKEN>`; o serviço consulta o ViaCEP e envia os dados ao webhook de entrada do Odoo. O endpoint `GET /health` verifica se o serviço iniciou.

## Variáveis no Railway

- `WEBHOOK_TOKEN`: segredo longo e aleatório, sem espaços ou `/`. A URL no webhook de saída do Odoo termina com esse segredo.
- `ODOO_WEBHOOK_URL`: URL completa do webhook **de entrada** gerada pelo Odoo, incluindo o identificador secreto gerado pelo Odoo. Não publicar essa URL no GitHub.

## Saída do Odoo para o Railway

Crie uma automação no modelo `crm.lead` com ação **Enviar notificação de webhook**. Inclua os campos `zip` e `id` (ou `_id`) e configure a URL `https://SEU-DOMINIO.up.railway.app/consultar-cep/SEU-WEBHOOK_TOKEN`. Ela pode ser uma ação manual ou disparar ao salvar quando o CEP mudar. A amostra precisa conter `_model: crm.lead`, `_id` ou `id`, e `zip`. Confirme a amostra antes de ativar. Em automações, evite disparar novamente quando o próprio endereço for atualizado.

## Entrada no Odoo para atualizar o lead

Crie outra automação no modelo `crm.lead` do tipo **Ao receber webhook**. Copie a URL gerada para a variável `ODOO_WEBHOOK_URL`. Defina o registro de destino com o ID recebido em `_id` e configure uma ação **Executar código** com o código abaixo. Ajuste os nomes dos campos se o seu lead tiver campos personalizados. As telas e permissões variam com a versão e o plano do Odoo.

```python
if record and payload.get('_model') == 'crm.lead':
    cep_atual = (record.zip or '').replace('-', '').replace(' ', '')
    if cep_atual == payload.get('zip'):
        valores = {}
        if payload.get('street'):
            valores['street'] = payload['street']
        if payload.get('city'):
            valores['city'] = payload['city']
        if payload.get('uf'):
            estado = env['res.country.state'].search([
                ('code', '=', payload['uf']),
                ('country_id.code', '=', 'BR'),
            ], limit=1)
            if estado:
                valores['state_id'] = estado.id
                valores['country_id'] = estado.country_id.id
        # Se houver campo personalizado de bairro, adicione-o após confirmar
        # seu nome técnico no Studio. Evite sobrescrever campos vazios.
        if valores:
            record.write(valores)
```

No campo **Registro de destino**, confira as instruções específicas da sua versão: ele precisa selecionar o lead com `payload['_id']` no modelo `crm.lead`. Uma expressão possível é `model.browse(int(payload.get('_id') or 0))`; confirme que o formulário aceita essa expressão. O código verifica o CEP atual antes de gravar, impedindo que uma resposta antiga sobrescreva um endereço após a troca de CEP.

## Verificação

1. Confirme que `/health` retorna `{"status":"ok"}`.
2. Use um lead de teste com CEP válido e confira a chamada no log do Railway.
3. Se a saída responder `enviado_ao_odoo` mas os campos não mudarem, confira a automação de entrada e o log do Odoo.

O ViaCEP retorna `erro: true` para CEP inexistente. A API gratuita é sujeita a limites de uso. Não coloque segredos no repositório nem em prints.
