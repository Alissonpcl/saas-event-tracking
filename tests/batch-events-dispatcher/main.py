#!/usr/bin/env python3
import requests
import json
import time
import random
import uuid
import signal
import sys
import os
from datetime import datetime
import argparse
from concurrent.futures import ThreadPoolExecutor

# Configurações padrão
DEFAULT_API_URL = "https://yvb68ofetd.execute-api.us-east-1.amazonaws.com/prod/events"
# DEFAULT_API_KEY = "sua-api-key"  # Remova se não estiver usando API Key
DEFAULT_BATCH_SIZE = 20  # Número de eventos por requisição
DEFAULT_REQUESTS_PER_SECOND = 1.0  # Requisições por segundo
DEFAULT_CONCURRENT_WORKERS = 5  # Número de workers paralelos
DEFAULT_LOG_FILE = "log_api_load_test_results.jsonl"

# Flag para controlar a execução
running = True

def generate_random_event():
    """Gera um evento de tracking aleatório"""
    event_types = ["page_view", "button_click", "form_submit", "video_play", "scroll"]
    pages = ["/home", "/products", "/about", "/contact", "/checkout"]
    
    return {
        "event_name": random.choice(event_types),
        "event_time": datetime.utcnow().isoformat(),
        "user_id": f"user_{uuid.uuid4().hex[:8]}",
        "session_id": f"session_{uuid.uuid4().hex}",
        "properties": {
            "page": random.choice(pages),
            "referrer": random.choice(["google", "facebook", "direct", "email", None]),
            "duration": random.randint(1, 300),
            "value": round(random.uniform(0, 100), 2)
        },
        "client_info": {
            "browser": random.choice(["Chrome", "Firefox", "Safari", "Edge"]),
            "os": random.choice(["Windows", "MacOS", "iOS", "Android"]),
            "screen_size": random.choice(["1920x1080", "1366x768", "375x812"])
        }
    }

def send_batch_request(api_url, api_key, batch_size, log_file):    
    """Envia uma requisição em lote para a API e registra os resultados"""
    # Gerar batch de eventos
    events = {"body":[]}
    events["body"] = [generate_random_event() for _ in range(batch_size)]
    
    # Preparar cabeçalhos
    headers = {
        'Content-Type': 'application/json'
    }
    if api_key:
        headers['x-api-key'] = api_key
    
    # Registrar hora de início
    start_time = time.time()
    
    try:
        # Enviar requisição
        response = requests.post(api_url, json=events, headers=headers)
        end_time = time.time()
        duration = end_time - start_time
        
        # Preparar dados para log
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "batch_size": batch_size,
            "duration_ms": f"{duration:.3f}",
            "status_code": response.status_code,
            "success": response.status_code == 200,
        }
        
        # Adicionar corpo da resposta se for JSON válido
        try:
            log_data["response"] = response.json()
        except json.JSONDecodeError:
            log_data["response"] = response.text[:200]  # Limitar tamanho do texto
        
        # Salvar no arquivo de log
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_data) + '\n')
        
        # Imprimir resumo no console
        print(f"[{datetime.utcnow().isoformat()}] Batch enviado: {batch_size} eventos, " 
              f"Status: {response.status_code}, Tempo: {duration:.3f}s")
        
        return True
    except Exception as e:
        # Registrar erro
        end_time = time.time()
        duration = end_time - start_time
        
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "batch_size": batch_size,
            "duration_ms": duration,
            "error": str(e),
            "success": False
        }
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_data) + '\n')
        
        print(f"[{datetime.utcnow().isoformat()}] ERRO: {str(e)}, Tempo: {duration:.3f}s")
        return False

def worker(api_url, api_key, batch_size, delay, log_file):     
    """Worker que envia requisições continuamente com intervalo definido"""
    while running:
        try:
            send_batch_request(api_url, api_key, batch_size, log_file)
            time.sleep(delay)
        except Exception as e:
            print(f"Erro no worker: {str(e)}")
            raise(e)

def signal_handler(sig, frame):
    """Manipulador para interrupção do usuário (Ctrl+C)"""
    global running
    print("\nInterrompendo teste de carga graciosamente. Aguarde o término das requisições em andamento...")
    running = False

def parse_arguments():
    """Processa os argumentos de linha de comando"""
    parser = argparse.ArgumentParser(description='Script de teste de carga para API de tracking de eventos')
    
    parser.add_argument('--url', default=DEFAULT_API_URL,
                        help=f'URL do endpoint da API (default: {DEFAULT_API_URL})')
    # parser.add_argument('--api-key', default=DEFAULT_API_KEY,
    #                     help='Chave de API (x-api-key)')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                        help=f'Número de eventos por batch (default: {DEFAULT_BATCH_SIZE})')
    parser.add_argument('--rps', type=float, default=DEFAULT_REQUESTS_PER_SECOND,
                        help=f'Requisições por segundo (default: {DEFAULT_REQUESTS_PER_SECOND})')
    parser.add_argument('--workers', type=int, default=DEFAULT_CONCURRENT_WORKERS,
                        help=f'Número de workers paralelos (default: {DEFAULT_CONCURRENT_WORKERS})')
    parser.add_argument('--log-file', default=DEFAULT_LOG_FILE,
                        help=f'Arquivo para salvar os resultados (default: {DEFAULT_LOG_FILE})')
    
    return parser.parse_args()

def print_test_summary(args):
    """Exibe um resumo do teste configurado"""
    print("\n" + "=" * 60)
    print("TESTE DE CARGA - API DE TRACKING DE EVENTOS")
    print("=" * 60)
    print(f"URL da API: {args.url}")
    print(f"Tamanho do batch: {args.batch_size} eventos")
    print(f"Workers paralelos: {args.workers}")
    print(f"Taxa de requisições: {args.rps * args.workers:.2f} req/s total")
    print(f"Taxa de eventos: {args.rps * args.workers * args.batch_size:.2f} eventos/s")
    print(f"Arquivo de log: {args.log_file}")
    print("=" * 60)
    print("Pressione Ctrl+C para interromper o teste\n")

def main():
    # Configurar handler para capturar Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Processar argumentos
    args = parse_arguments()
    
    # Calcular o delay entre requisições para cada worker
    delay = 1.0 / args.rps if args.rps > 0 else 0
    
    # Garantir que o diretório do arquivo de log exista
    log_dir = os.path.dirname(args.log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Inicializar o arquivo de log
    with open(args.log_file, 'w') as f:
        f.write("")  # Limpar o arquivo
    
    # Exibir resumo do teste
    print_test_summary(args)
    
    # Iniciar workers
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = []
        for _ in range(args.workers):            
            futures.append(
                executor.submit(
                    worker, 
                    args.url,                     
                    None, # args.api_key,
                    args.batch_size, 
                    delay, 
                    args.log_file
                )
            )
    
    print("\nTeste finalizado!")
    print(f"Resultados salvos em: {args.log_file}")

if __name__ == "__main__":
    main()