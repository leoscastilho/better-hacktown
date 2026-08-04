# Better HackTown

> **Um app da comunidade para navegar pela programação do HackTown em Santa Rita do Sapucaí**

Um Progressive Web App (PWA) moderno para navegar pelos eventos do HackTown com uma experiência de usuário aprimorada e sistema de scraping assíncrono otimizado.

## 🚀 Funcionalidades

- **Scraping Assíncrono**: Sistema de scraping otimizado com requisições concorrentes e retry automático
- **Progressive Web App**: PWA instalável com capacidades offline
- **Design Responsivo**: Design mobile-first que funciona em todos os dispositivos
- **Sistema de Localização Inteligente**: Mapeamento centralizado de locais com suporte a múltiplos nomes
- **Detecção de Ambiente**: Configurações adaptáveis para CI/CD e desenvolvimento local
- **Performance Rápida**: Estratégias otimizadas de carregamento e cache
- **Suporte a Múltiplos Anos**: Dados organizados por ano; o app carrega apenas um ano por vez
- **Deploy Flexível**: Suporte para GitHub Actions e Docker com automação completa

## 📋 Estrutura do Projeto

```
better-hacktown/
├── scrape_hacktown.py          # Sync multi-ano: dispatcher (escolhe o provider por ano)
├── sync_common.py              # Núcleo compartilhado: formato de saída, filtros, localizações
├── provider_yazo.py            # Provider 2025 — API Yazo (paginada por dia)
├── provider_supabase.py        # Provider 2026 — Supabase/PostgREST (tudo em uma requisição)
├── add_location.py             # Helper interativo para adicionar localizações
├── index.html                  # Frontend PWA
├── service-worker.js           # Service worker PWA para funcionalidade offline
├── logo.png                    # Logo/ícone do app
├── requirements.txt            # Dependências Python (requests, aiohttp)
├── Dockerfile                  # Container Docker para scraping
├── docker-compose.yml          # Orquestração Docker
├── run-scraper.sh              # Script de execução Docker
├── docker-scraper.sh           # Script interno do container
├── DOCKER_SETUP.md             # Guia de configuração Docker
├── .env.example                # Template de variáveis de ambiente
├── .gitignore                  # Arquivos ignorados pelo Git
├── config/                     # Configuração (compartilhada entre scraper e frontend)
│   ├── years.json                  # Registro de anos: activeYear + datas/API por ano
│   ├── 2025/
│   │   └── locations_config.json   # Mapeamentos de localização do ano 2025
│   └── 2026/
│       └── locations_config.json   # Mapeamentos de localização do ano 2026 (modelo)
├── events/                     # Dados de eventos raspados, um subdiretório por ano
│   └── 2025/                       # (events/<ano>/)
│       ├── hacktown_events_*.json      # Arquivos de eventos diários
│       ├── locations.json              # Dados de localizações (auto-gerado)
│       ├── filter_locations.json       # Lista de localizações para filtros
│       ├── filter_speakers.json        # Lista de palestrantes para filtros
│       └── summary.json                # Estatísticas resumidas de eventos
├── logs/                       # Logs de execução
├── .github/workflows/          # Workflows GitHub Actions
│   └── scrape-events.example       # Template de workflow
└── README.md                   # Este arquivo
```

## 🗓️ Suporte a Múltiplos Anos

Os dados são organizados por ano em `events/<ano>/`, e a configuração de cada ano
fica em `config/years.json` (registro central) e `config/<ano>/locations_config.json`
(mapeamentos de localização). O arquivo `config/years.json` é a **única fonte de
verdade**, compartilhada pelo scraper e pelo frontend.

- **`config/years.json`** declara `activeYear` (o ano padrão exibido no app) e, para
  cada ano, seu `label`, se está `enabled`, as `dates` do evento e os parâmetros de `api`.
- O **frontend carrega apenas um ano por vez** (o `activeYear`, ou o ano do parâmetro de
  URL `#year=`), evitando lentidão. Um seletor de ano aparece na barra lateral quando há
  mais de um ano habilitado.
- O **scraper** raspa o `activeYear` por padrão; use `--year <ano>` para um ano específico
  ou `--all-years` para todos os anos configurados.

### Arquitetura do sync (um provider por ano)

Cada ano pode vir de uma API completamente diferente, então a busca é feita por
**providers** intercambiáveis, mas a saída é sempre idêntica:

- **`scrape_hacktown.py`** — dispatcher: lê `config/years.json`, escolhe o provider do ano
  (campo `provider`) e o executa através do núcleo compartilhado.
- **`sync_common.py`** — núcleo compartilhado: normalização de localização e geração de
  `hacktown_events_<data>.json`, `filter_locations.json`, `filter_speakers.json`,
  `locations.json` e `summary.json` (mesmo formato para todos os anos).
- **`provider_yazo.py`** (2025) — API Yazo, paginada por dia.
- **`provider_supabase.py`** (2026) — Supabase/PostgREST; todo o cronograma em uma
  requisição, transformado no formato canônico (mesmos campos/filtros do 2025).

Cada provider apenas busca e converte os eventos; `sync_common` cuida de salvar tudo no
mesmo formato. Para adicionar uma fonte nova, escreva um `provider_*.py` com `configure()`
e `fetch(dates)` e aponte o `provider` do ano para ele.

**IDs estáveis (`REMAP_IDS`)**: fontes cujo id nativo é longo (ex.: os UUIDs do 2026)
podem definir `REMAP_IDS = True` no provider. O dispatcher então mapeia cada UUID para um
**id inteiro estável** (via `events/<ano>/id_map.json`, versionado) que nunca muda depois
de atribuído — mantendo favoritos (localStorage) e links de compartilhamento curtos. O
mapa também guarda um hash do conteúdo de cada evento, então o sync **só reescreve os dias
que realmente mudaram** (sem churn/commits desnecessários); eventos novos ganham novos ids.

**Segurança dos dados** (para providers com `REMAP_IDS`):

- **Guarda contra apagamento em massa**: se mais de `HACKTOWN_GUARD_MAX_REMOVED` (padrão
  **30%**) dos eventos ativos sumirem do feed numa única execução (havendo pelo menos
  `HACKTOWN_GUARD_MIN_EVENTS`, padrão 20), o sync **aborta sem escrever nada** e sai com
  erro — protegendo contra um feed adulterado/quebrado que apagaria tudo. Use `--force`
  (ou `HACKTOWN_FORCE=1`) para uma mudança grande legítima.
- **Remoção suave (soft delete)**: um evento que deixa de aparecer no feed **nunca é
  apagado**. Ele ganha um `removed_at` no `id_map` e é mantido no arquivo do dia com
  `removed: true` (o dado é preservado); o frontend não exibe eventos `removed`. Se voltar
  a aparecer, é reativado (`removed_at` limpo) com dados novos.

### Adicionar um novo ano (ex.: 2026)

1. Adicione/edite a entrada do ano em `config/years.json` com as `dates` e o bloco `api`
   corretos e defina `"enabled": true`.
2. Ajuste os mapeamentos de local em `config/2026/locations_config.json` (já criado como
   modelo a partir de 2025).
3. Rode o scraper para o ano: `python scrape_hacktown.py --year 2026`.
4. Para tornar 2026 o padrão do app, defina `"activeYear": "2026"` em `config/years.json`.

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

- **`config/<ano>/locations_config.json`**: Arquivo mestre com os mapeamentos de localização do ano (um por ano)
- **`events/<ano>/locations.json`**: Arquivo auto-gerado usado pelo frontend (não editar manualmente)

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
python add_location.py            # usa o activeYear de config/years.json
python add_location.py --year 2026  # edita um ano específico
```

O script helper fornece uma interface interativa para:
- Adicionar novas localizações com múltiplos nomes possíveis
- Listar localizações existentes e suas configurações
- Validar entrada e prevenir duplicatas

#### Método 2: Edição Manual
Edite `config/<ano>/locations_config.json` diretamente seguindo a estrutura acima.

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
Os arquivos são carregados a partir do diretório do ano ativo (`events/<ano>/`):
```javascript
// Carregar localizações de filtro (ex.: events/2025/filter_locations.json)
fetch(`./events/${currentYear}/filter_locations.json`)
  .then(response => response.json())
  .then(data => populateLocationFilter(data.locations));

// Carregar palestrantes de filtro
fetch(`./events/${currentYear}/filter_speakers.json`)
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

### Arquivos de Eventos (por ano, em `events/<ano>/`)
- `hacktown_events_YYYY-MM-DD.json`: Programações de eventos diárias
- `locations.json`: Informações de locais e venues (auto-gerado)
- `filter_locations.json`: Lista de localizações únicas para filtros dropdown
- `filter_speakers.json`: Lista de palestrantes únicos para filtros dropdown
- `summary.json`: Estatísticas de eventos e metadados
- `id_map.json`: Mapa `UUID → id inteiro estável` + hash e baselines de cada evento (não editar)
- `updates.json`: Histórico de alterações dos eventos (ver abaixo)

### Histórico de alterações (`events/<ano>/updates.json`)

Log **append-only** com as mudanças que interessam a quem vai ao evento — a base
para o futuro sistema de notificações do frontend. A cada sync, novas linhas são
acrescentadas com o horário da ocorrência:

| `change`  | Quando |
|-----------|--------|
| `removed` | Evento cancelado (sumiu do feed) |
| `place`   | Local alterado (inclui `from`/`to`) |
| `time`    | Horário alterado (`start_time` e/ou `end_time`, com `from`/`to`) |

```json
{ "at": "2026-08-04T08:25:18-03:00", "id": 27, "change": "place",
  "date": "2026-09-03", "title": "…", "from": "FAI - Sala 8", "to": "ETE - Sala 12" }
```

- Outras alterações (título, descrição…) **não** são registradas.
- Um evento cancelado que **volta** a aparecer não gera registro novo e ainda
  **remove** o aviso de cancelamento anterior da lista — o ciclo cancelar →
  reativar não deixa rastro. Se for cancelado de novo, um aviso novo é criado.
- O mesmo evento pode acumular vários registros ao longo do tempo.
- Nada é gravado quando a guarda de segurança aborta o sync; um sync sem mudanças
  deixa o arquivo intacto. O log é limitado às últimas 2000 entradas.

### Integração com API
O endpoint, o provider e os parâmetros são configurados por ano em `config/years.json`.

- **2025** (`provider: yazo`) — API Yazo, paginada por dia:
  ```
  https://hacktown-2025-ss-v2.api.yazo.com.br/public/schedules
  ```
- **2026** (`provider: supabase`) — Supabase/PostgREST (embed Lovable em
  `hacktown.com.br/programacao/`); todo o cronograma em uma requisição:
  ```
  https://xbsooiedncsrmrhjasvk.supabase.co/rest/v1/events
  ```

### Datas dos Eventos
As datas de cada ano ficam em `config/years.json` (`years.<ano>.dates`).
- **2025**: 30/07 a 03/08 (5 dias)
- **2026**: 03/09 a 06/09 (4 dias)

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
- Use `python add_location.py --year <ano>` para adicionar novas localizações
- Verifique o arquivo `events/<ano>/summary.json` para localizações não mapeadas
- Edite `config/<ano>/locations_config.json` manualmente se necessário

**Problemas de Docker:**
- Verifique se o arquivo `.env` está configurado corretamente
- Confirme se o GITHUB_TOKEN tem permissões adequadas
- Consulte logs em `./logs/` para detalhes de erro

### Testando Configurações

```bash
# Testar mapeamentos de localização (para um ano específico)
python -c "
import scrape_hacktown as s
reg = s.load_years_registry()
s.configure_for_year('2025', reg)   # carrega config/2025/locations_config.json
s.load_location_config()
print('Mapeamentos carregados:', len(s.location_mappings))
"

# Testar scraper em modo debug (ano ativo por padrão)
python scrape_hacktown.py
# ...ou um ano específico:
python scrape_hacktown.py --year 2026
```

## 🤝 Contribuindo

1. Faça fork do repositório
2. Crie uma branch de feature (`git checkout -b feature/funcionalidade-incrivel`)
3. Commit suas mudanças (`git commit -m 'Adiciona funcionalidade incrível'`)
4. Push para a branch (`git push origin feature/funcionalidade-incrivel`)
5. Abra um Pull Request

---

## 📄 Licença

Este projeto é de código aberto sob a **Licença MIT** — veja o arquivo [LICENSE](LICENSE)
para o texto completo. Você pode usar, copiar, modificar e distribuir o código
livremente, mantendo o aviso de copyright e a permissão.

---

**Feito com ❤️ para a comunidade HackTown**

### 🔗 Links Úteis

- [HackTown](https://hacktown.com.br)
- [Docker Setup Guide](DOCKER_SETUP.md)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)