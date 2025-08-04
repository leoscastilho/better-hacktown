# Better HackTown 2025

> 🤖 **Este aplicativo foi desenvolvido utilizando o Amazon Q para o HackTown 2025 em Santa Rita do Sapucaí**

Um Progressive Web App (PWA) moderno para navegar pelos eventos do HackTown 2025 com uma experiência de usuário aprimorada e sistema de scraping assíncrono otimizado.

## 🚀 Funcionalidades

- **Scraping Assíncrono**: Sistema de scraping otimizado com requisições concorrentes e retry automático
- **Progressive Web App**: PWA instalável com capacidades offline
- **Design Responsivo**: Design mobile-first que funciona em todos os dispositivos
- **Sistema de Localização Inteligente**: Mapeamento centralizado de locais com suporte a múltiplos nomes
- **Detecção de Ambiente**: Configurações adaptáveis para CI/CD e desenvolvimento local
- **Performance Rápida**: Estratégias otimizadas de carregamento e cache
- **Deploy Flexível**: Suporte para GitHub Actions e Docker com automação completa

## 📋 Estrutura do Projeto

```
better-hacktown/
├── scrape_hacktown.py          # Script principal de scraping (assíncrono)
├── locations_config.json       # Configuração centralizada de localizações
├── add_location.py            # Helper interativo para adicionar localizações
├── index.html                 # Frontend PWA
├── service-worker.js          # Service worker PWA para funcionalidade offline
├── logo.png                   # Logo/ícone do app
├── requirements.txt           # Dependências Python (requests, aiohttp)
├── Dockerfile                 # Container Docker para scraping
├── docker-compose.yml         # Orquestração Docker
├── run-scraper.sh            # Script de execução Docker
├── docker-scraper.sh         # Script interno do container
├── DOCKER_SETUP.md           # Guia de configuração Docker
├── .env.example              # Template de variáveis de ambiente
├── .gitignore                # Arquivos ignorados pelo Git
├── events/                   # Dados de eventos raspados
│   ├── hacktown_events_*.json    # Arquivos de eventos diários
│   ├── locations.json           # Dados de localizações (auto-gerado)
│   ├── filter_locations.json    # Lista de localizações para filtros
│   ├── filter_speakers.json     # Lista de palestrantes para filtros
│   └── summary.json            # Estatísticas resumidas de eventos
├── logs/                     # Logs de execução
├── .github/workflows/        # Workflows GitHub Actions
│   └── scrape-events.example    # Template de workflow
└── README.md                 # Este arquivo
```

## 🛠️ Instalação e Configuração

### Pré-requisitos

- Python 3.9+ (para suporte ao zoneinfo)
- Docker e Docker Compose (para deploy automatizado)
- Navegador moderno para recursos PWA

### Opção 1: Execução Local

1. **Clone o repositório**
   ```bash
   git clone <url-do-repositório>
   cd better-hacktown
   ```

2. **Instale as dependências Python**
   ```bash
   pip install -r requirements.txt
   ```

3. **Execute o scraper**
   ```bash
   python scrape_hacktown.py
   ```

4. **Sirva a aplicação web**
   ```bash
   # Usando o servidor integrado do Python
   python -m http.server 8000
   
   # Ou usando qualquer outro servidor de arquivos estáticos
   npx serve .
   ```

5. **Acesse a aplicação**
   Abra seu navegador e navegue para `http://localhost:8000`

### Opção 2: Deploy com Docker

Para configuração automatizada com Docker, consulte o [DOCKER_SETUP.md](DOCKER_SETUP.md) para instruções detalhadas.

**Resumo rápido:**

1. **Configure as variáveis de ambiente**
   ```bash
   cp .env.example .env
   # Edite .env com suas configurações
   ```

2. **Execute o scraper**
   ```bash
   ./run-scraper.sh
   ```

## 🗺️ Sistema de Gerenciamento de Localizações

O projeto utiliza um **sistema centralizado de configuração de localizações** que elimina a necessidade de atualizar mapeamentos em múltiplos lugares.

### Arquivos de Configuração

- **`locations_config.json`**: Arquivo mestre com todos os mapeamentos de localização
- **`events/locations.json`**: Arquivo auto-gerado usado pelo frontend (não editar manualmente)

### Estrutura de Configuração

```json
{
  "location_mappings": {
    "location_key": {
      "possible_names": ["VARIAÇÃO NOME 1", "VARIAÇÃO NOME 2"],
      "filter_location": "Nome Padronizado para Exibição",
      "near_location": "Área Geográfica",
      "gmaps": "https://maps.app.goo.gl/..."
    }
  }
}
```

### Funcionalidades Principais

- **Suporte a Múltiplos Nomes**: Cada localização pode ter várias `possible_names` que mapeiam para o mesmo local padronizado
- **Case Insensitive**: Toda correspondência é feita sem distinção de maiúsculas/minúsculas
- **Deduplicação Automática**: Diferentes variações de nomes da API são automaticamente consolidadas
- **Manutenção Fácil**: Adicione novas variações de nomes sem duplicar dados de localização

### Adicionando Novas Localizações

#### Método 1: Script Helper Interativo (Recomendado)
```bash
python add_location.py
```

O script helper fornece uma interface interativa para:
- Adicionar novas localizações com múltiplos nomes possíveis
- Listar localizações existentes e suas configurações
- Validar entrada e prevenir duplicatas

#### Método 2: Edição Manual
Edite `locations_config.json` diretamente seguindo a estrutura acima.

### Categorias de Localização

- **Inatel e Arredores**: Campus e locais próximos
- **ETE e Arredores**: Área da escola técnica
- **Praça e Arredores**: Praça central e área do centro
- **Other**: Localizações não mapeadas ou desconhecidas

## 🔍 Arquivos de Dados de Filtro

O scraper gera automaticamente arquivos de dados de filtro para popular listas dropdown na aplicação web:

### Localizações de Filtro (`filter_locations.json`)
Contém uma lista de nomes únicos de localização extraídos de todos os eventos.

### Palestrantes de Filtro (`filter_speakers.json`)
Contém uma lista de nomes únicos de palestrantes extraídos de todos os eventos.

### Uso na Aplicação Web
```javascript
// Carregar localizações de filtro
fetch('./events/filter_locations.json')
  .then(response => response.json())
  .then(data => populateLocationFilter(data.locations));

// Carregar palestrantes de filtro
fetch('./events/filter_speakers.json')
  .then(response => response.json())
  .then(data => populateSpeakerFilter(data.speakers));
```

## ⚡ Sistema de Scraping Otimizado

### Detecção de Ambiente

O scraper detecta automaticamente o ambiente de execução e ajusta suas configurações:

- **Ambiente CI/CD**: Configurações conservadoras (1 requisição por vez, delays maiores)
- **Desenvolvimento Local**: Configurações otimizadas (2 requisições concorrentes)
- **Docker com FORCE_LOCAL_MODE**: Força configurações locais mesmo em containers

### Funcionalidades do Scraper

- **Requisições Assíncronas**: Processamento concorrente para melhor performance
- **Retry Automático**: Lógica de retry com backoff exponencial
- **Rate Limiting Inteligente**: Respeita limites da API automaticamente
- **Logging Abrangente**: Logs detalhados para debugging e monitoramento
- **Cache de Localização**: Sistema de cache para otimizar mapeamentos

### Configurações por Ambiente

```python
# Ambiente CI/CD
MAX_CONCURRENT_REQUESTS = 1
RETRY_DELAY = 20s
MAX_RETRIES = 3
REQUEST_TIMEOUT = 60s

# Desenvolvimento Local
MAX_CONCURRENT_REQUESTS = 2
RETRY_DELAY = 5s
MAX_RETRIES = 5
REQUEST_TIMEOUT = 30s
```

## 🔄 Automação e Deploy

### GitHub Actions (Opcional)

O projeto inclui um template de workflow do GitHub Actions (`.github/workflows/scrape-events.example`) para automação:

- **Agendamento**: Executa a cada 4 horas
- **Trigger Manual**: Pode ser acionado via interface do GitHub
- **Cache Busting**: Atualiza automaticamente versões de cache do PWA
- **Commits Inteligentes**: Só faz commit quando há mudanças reais

### Docker (Recomendado)

Sistema completo de containerização para deploy em servidor próprio:

- **Container Isolado**: Ambiente Python isolado e reproduzível
- **Integração Git**: Clona, atualiza e faz push automaticamente
- **Logging**: Sistema de logs com rotação automática
- **Cron Integration**: Fácil integração com crontab do sistema

### Configuração de Cron

```bash
# Executa a cada 4 horas
0 */4 * * * /path/to/better-hacktown/run-scraper.sh
```

## 📊 Estrutura de Dados

### Arquivos de Eventos
- `hacktown_events_YYYY-MM-DD.json`: Programações de eventos diárias
- `locations.json`: Informações de locais e venues (auto-gerado)
- `filter_locations.json`: Lista de localizações únicas para filtros dropdown
- `filter_speakers.json`: Lista de palestrantes únicos para filtros dropdown
- `summary.json`: Estatísticas de eventos e metadados

### Integração com API
O scraper se conecta a:
```
https://hacktown-2025-ss-v2.api.yazo.com.br/public/schedules
```

### Datas dos Eventos
- 2025-07-30 (Dia 1)
- 2025-07-31 (Dia 2)
- 2025-08-01 (Dia 3)
- 2025-08-02 (Dia 4)
- 2025-08-03 (Dia 5)

## 🎨 Personalização

### Estilização
Modifique o CSS no `index.html` para personalizar a aparência.

### Analytics
Atualize os IDs do Google Analytics e Tag Manager no `index.html`:
```javascript
gtag('config', 'SEU-ID-GA');
// ID GTM no script do Tag Manager
```

### Configuração PWA
Edite o manifest e service worker para personalização do PWA:
- Nome e descrição do app
- Cores do tema
- Estratégias de cache
- Comportamento offline

## 📱 Funcionalidades PWA

- **Instalável**: Adicionar à tela inicial em dispositivos móveis
- **Suporte Offline**: Eventos em cache disponíveis sem internet
- **Experiência Similar a App**: Modo tela cheia e sensação nativa
- **Carregamento Rápido**: Estratégias de cache do service worker
- **Responsivo**: Funciona em desktop, tablet e mobile

## 🔧 Solução de Problemas

### Problemas Comuns

**Erro de Rate Limiting:**
- O scraper detecta automaticamente e ajusta configurações
- Em ambiente CI, usa configurações ultra-conservadoras
- Use `FORCE_LOCAL_MODE=true` em Docker para configurações otimizadas

**Localizações Não Mapeadas:**
- Use `python add_location.py` para adicionar novas localizações
- Verifique o arquivo `summary.json` para localizações não mapeadas
- Edite `locations_config.json` manualmente se necessário

**Problemas de Docker:**
- Verifique se o arquivo `.env` está configurado corretamente
- Confirme se o GITHUB_TOKEN tem permissões adequadas
- Consulte logs em `./logs/` para detalhes de erro

### Testando Configurações

```bash
# Testar mapeamentos de localização
python -c "
import json
from scrape_hacktown import normalize_and_locate, load_location_config
load_location_config()
print('Testando variações de localização...')
"

# Testar scraper em modo debug
python scrape_hacktown.py
```

## 🤝 Contribuindo

1. Faça fork do repositório
2. Crie uma branch de feature (`git checkout -b feature/funcionalidade-incrivel`)
3. Commit suas mudanças (`git commit -m 'Adiciona funcionalidade incrível'`)
4. Push para a branch (`git push origin feature/funcionalidade-incrivel`)
5. Abra um Pull Request

---

**Feito com ❤️ para a comunidade HackTown 2025 com a assistência do Amazon Q**

### 🔗 Links Úteis

- [HackTown 2025](https://hacktown.com.br)
- [Docker Setup Guide](DOCKER_SETUP.md)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)