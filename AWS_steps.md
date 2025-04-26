# AWS Implementation Guide

## Criação do Bucket S3

1. Acesse o console da AWS e navegue até o serviço S3
1. Clique em "Criar bucket"
1. Configure o bucket:
    1. Nome: saas-event-tracking (use um nome único)
    1. Região: selecione a mesma região para todos os serviços (ex: us-east-1)
    1. Configurações de acesso: Bloquear acesso público (recomendado)
    1. Versionamento: Opcional (habilite se desejar histórico de versões)
    1. Criptografia: Habilite criptografia padrão SSE-S3


## Função lambda

### Criar a Função Lambda

1. No console AWS, navegue até o serviço Lambda
1. Clique em "Criar função"
1. Selecione "Criar do zero" (Author from scratch)
1. Configure os detalhes básicos:
    1. Nome da função: event-tracking-processor
    1. Runtime: Python 3.11 (ou versão disponível)
    1. Arquitetura: x86_64
1. Em "Permissões", selecione "Criar uma nova função com permissões básicas do Lambda"
    1. Isso criará uma função com permissões básicas de CloudWatch Logs
1. Clique em "Criar função"

**Adicionar Permissões de S3 à Função IAM**

Depois que a função Lambda for criada:

1. Na página da função Lambda, role até "Configuração" e clique em "Permissões"
1. Clique no nome da função de execução para abrir no console IAM
1. No console IAM, clique em "Adicionar permissões" e depois em "Criar política em linha"
1. Selecione a guia "JSON" e insira a política abaixo (você pode também manter o que já existe de permissões adicionando apenas o conteúdo de *Statement*):

```json
json{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::saas-event-tracking/*",
                "arn:aws:s3:::saas-event-tracking"
            ]
        }
    ]
}
```

1. Clique em "Revisar política"
1. Dê um nome à política, como LambdaS3EventTracking
1. Clique em "Criar política"

### Configurar o Código da Função

1. Na tela da função recém-criada, role para baixo até a seção "Código da função"
1. No editor de código, substitua o código padrão pelo código Python abaixo:

```python
import json
import boto3
import time
import os
from datetime import datetime

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'your-event-tracking-bucket')  # Configure nas variáveis de ambiente

def lambda_handler(event, context):
    try:
        # Obter o corpo da requisição
        body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        
        # Validar se é um evento único ou um batch
        events = body if isinstance(body, list) else [body]
        
        # Adicionar timestamp de processamento se não existir
        for evt in events:
            if 'event_time' not in evt:
                evt['event_time'] = datetime.utcnow().isoformat()
        
        # Definir caminho do arquivo com particionamento
        now = datetime.utcnow()
        year, month, day, hour = now.year, now.month, now.day, now.hour
        
        # Criar um nome de arquivo único
        file_name = f"events_{time.time_ns()}.json"
        key = f"events/year={year}/month={month:02d}/day={day:02d}/hour={hour:02d}/{file_name}"
        
        # Salvar eventos no S3
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=json.dumps(events),
            ContentType='application/json'
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',  # Permitir CORS
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': f'Processado(s) {len(events)} evento(s) com sucesso',
                'events_count': len(events)
            })
        }
        
    except Exception as e:
        print(f"Erro: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': f'Erro ao processar eventos: {str(e)}'
            })
        }
```        

### Configurar Variáveis de Ambiente

1. Role para baixo até a seção "Variáveis de ambiente"
1. Clique em "Editar"
1. Adicione uma nova variável:
    1. Chave: BUCKET_NAME
    1. Valor: Nome do seu bucket S3 (ex: your-company-event-tracking)
1. Clique em "Salvar"

### Configurar as Configurações da Função

1. Role para cima e clique na aba "Configuração"
1. Clique em "Configurações gerais" e depois em "Editar"
1. Configure:
    1. Memória: 128 MB (suficiente para este caso)
    1. Timeout: 10 segundos (ajuste conforme necessário)
    1. Simultaneidade reservada: (deixe como padrão)
1. Clique em "Salvar"

### Testar a Função

1. Volte à página da função Lambda
1. Clique em "Teste" na seção lateral Deploy
1. Clique em "Criar novo evento"
1. Configure o evento de teste:
    1. Nome do evento: TestEventAPI
    1. Corpo do evento:

```json
{
  "body": [
    {
      "event_name": "test_event",
      "user_id": "test_user_123",
      "properties": {
        "action": "test_lambda"
      }
    }
  ]
}
```

1. Clique em "Salvar" e depois em "Testar"
1. Verifique se o teste é bem-sucedido e se o arquivo foi criado no bucket S3

## API Getaway

### Criar uma Nova API

1. Na página inicial do API Gateway, clique no botão "Criar API"
1. Selecione "API REST" e depois "Criar"
1. Na tela de configuração:
    1. Escolha "Nova API"
    1. Nome da API: saas-event-tracking-api    
    1. Tipo de endpoint: Regional
1. Clique em "Criar API"

### Criar um Recurso

1. Com a API criada, você estará na tela de recursos
1. Clique no botão "Criar recurso"
1. Configure o recurso:
    1. Desmarque a opção Proxy resource
    1. Nome do recurso: events
    1. Caminho do recurso: /
    1. Habilite a opção CORS
1. Clique em "Criar recurso"

### Criar o Método POST

1. Com o recurso /events selecionado, clique em "Criar método"
1. No menu suspenso, selecione "POST" e clique no ícone de confirmação
1. Configure o método:
    1. Tipo de integração: Função Lambda
    1. Função Lambda: Digite o nome da sua função Lambda (event-tracking-processor)
    1. Tempo limite padrão: deixe como padrão (29 segundos)
1. Clique em Criar método

### Configurar CORS (Cross-Origin Resource Sharing)

1. Selecione o recurso /events
1. Clique no menu "Ações" e selecione "Habilitar CORS"
1. Configure as opções de CORS:
    1. Métodos ACCESS-CONTROL-ALLOW-ORIGIN: * (ou seu domínio específico para maior segurança)
    1. ACCESS-CONTROL-ALLOW-HEADERS: Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token
    1. ACCESS-CONTROL-ALLOW-METHODS: Selecione POST e OPTIONS
1. Clique em "Habilitar CORS e substituir os métodos existentes"
1. Confirme clicando em "Sim, substituir existente"

### Implantar a API

1. No menu "Ações", selecione "Implantar API"
1. Na janela de implantação:
    1. Estágio: [Novo estágio]
    1. Nome do estágio: **prod** (ou outro nome de sua escolha)
    1. Descrição do estágio: **Ambiente de produção**
1. Clique em "Implantar"

### Obter URL da API

1. No menu lateral, clique em "Estágios"
1. Selecione o estágio prod
1. Anote a URL exibida na parte superior da página (Invocar URL)