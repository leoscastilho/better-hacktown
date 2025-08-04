# Better HackTown 2025

> 🤖 **Este aplicativo foi desenvolvido utilizando o Amazon Q para o HackTown 2025 em Santa Rita do Sapucaí**

Um Progressive Web App (PWA) moderno para navegar pelos eventos do HackTown 2025 com uma experiência de usuário aprimorada.

## 🚀 Funcionalidades

- **Scraping de Eventos**: Scraping assíncrona de eventos do HackTown 2025 da API oficial
- **Progressive Web App**: PWA instalável com capacidades offline
- **Design Responsivo**: Design mobile-first que funciona em todos os dispositivos
- **Atualizações em Tempo Real**: Sincronização automatizada de dados de eventos
- **Performance Rápida**: Estratégias otimizadas de carregamento e cache
- **Integração com Analytics**: Integração com Google Analytics e Tag Manager

## 📋 Estrutura do Projeto

```
better-hacktown/
├── scrape_hacktown.py      # Script principal de Scraping (assíncrono)
├── index.html              # Frontend PWA
├── service-worker.js       # Service worker PWA para funcionalidade offline
├── logo.png               # Logo/ícone do app
├── requirements.txt        # Dependências Python
├── events/                # Dados de eventos raspados
│   ├── hacktown_events_*.json  # Arquivos de eventos diários
│   ├── locations.json     # Dados de localizações de eventos
│   ├── filter_locations.json  # Lista de localizações únicas para filtros
│   ├── filter_speakers.json   # Lista de palestrantes únicos para filtros
│   └── summary.json       # Estatísticas resumidas de eventos
└── README.md              # Este arquivo
```

## 🛠️ Instalação

### Pré-requisitos

- Python 3.9+ (para suporte ao zoneinfo)
- Navegador moderno para recursos PWA

### Configuração

1. **Clone o repositório**
   ```bash
   git clone <url-do-repositório>
   cd better-hacktown
   ```

2. **Instale as dependências Python**
   ```bash
   pip install -r requirements.txt
   ```

3. **Execute o raspador**
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

## 🔍 Filter Data Files

The scraper automatically generates filter data files to populate dropdown lists in the web application:

### Filter Locations (`filter_locations.json`)
Contains a list of unique location names extracted from all events:
```json
{
  "generated_at": "2025-08-04T10:30:00-03:00",
  "total_locations": 15,
  "locations": [
    "Auditório Principal",
    "Sala de Workshops",
    "Espaço Networking",
    "..."
  ]
}
```

### Filter Speakers (`filter_speakers.json`)
Contains a list of unique speaker names extracted from all events:
```json
{
  "generated_at": "2025-08-04T10:30:00-03:00",
  "total_speakers": 42,
  "speakers": [
    "Ana Silva",
    "João Santos",
    "Maria Oliveira",
    "..."
  ]
}
```

### Usage in Web Application
These files can be loaded by the frontend to populate filter dropdowns:
```javascript
// Load filter locations
fetch('./events/filter_locations.json')
  .then(response => response.json())
  .then(data => populateLocationFilter(data.locations));

// Load filter speakers
fetch('./events/filter_speakers.json')
  .then(response => response.json())
  .then(data => populateSpeakerFilter(data.speakers));
```

### Automatic Generation
- Files are automatically generated each time the scraper runs
- Data is extracted from all successfully scraped events
- Lists are sorted alphabetically for consistent ordering
- Duplicate entries are automatically removed
- Empty or invalid entries are filtered out

## 🗺️ Location Management

The application uses a **centralized location configuration system** that eliminates the need to update location mappings in multiple places.

### Configuration Files

- **`locations_config.json`**: Master configuration file containing all location mappings
- **`events/locations.json`**: Auto-generated file used by the frontend (do not edit manually)

### Location Configuration Structure

```json
{
  "location_mappings": {
    "API_LOCATION_KEY": {
      "filter_location": "Standardized Name",
      "near_location": "Geographical Area",
      "gmaps": "https://maps.app.goo.gl/..."
    }
  }
}
```

### Adding New Locations

#### Method 1: Manual Editing
Edit `locations_config.json` directly and add new mappings following the structure above.

### Location Categories

- **Inatel e Arredores**: Campus and nearby venues
- **ETE e Arredores**: Technical school area  
- **Praça e Arredores**: Central plaza and downtown area
- **Other**: Unmapped or unknown locations

### Workflow

1. **Add new location**: Use `python add_location.py` or edit `locations_config.json`
2. **Run scraper**: Execute `python scrape_hacktown.py`
3. **Auto-generation**: The scraper automatically updates `events/locations.json`
4. **Frontend sync**: The web app uses the updated location data

### Benefits

- ✅ **Single source of truth**: All location data in one file
- ✅ **Automatic sync**: Frontend locations.json is auto-generated
- ✅ **No duplication**: Update once, works everywhere
- ✅ **Easy maintenance**: Interactive helper for adding locations
- ✅ **Version control friendly**: Clean diffs when locations change

## 📊 Estrutura de Dados

### Arquivos de Eventos
- `hacktown_events_YYYY-MM-DD.json`: Programações de eventos diárias
- `locations.json`: Informações de locais e venues
- `filter_locations.json`: Lista de localizações únicas para filtros dropdown
- `filter_speakers.json`: Lista de palestrantes únicos para filtros dropdown
- `summary.json`: Estatísticas de eventos e metadados

### Integração com API
O raspador se conecta a:
```
https://hacktown-2025-ss-v2.api.yazo.com.br/public/schedules
```

## 🔄 Automação

### Workflow do GitHub Actions

O projeto inclui um workflow automatizado do GitHub Actions (`.github/workflows/scrape-events.yml`) que mantém os dados de eventos atualizados e a aplicação web atualizada automaticamente.

#### Configuração do Workflow

**Gatilhos:**
- **Agendado**: Executa a cada 4 horas (`0 */4 * * *`)
- **Manual**: Pode ser acionado manualmente via interface do GitHub Actions
- **Push**: Executa automaticamente quando `scrape_hacktown.py` ou o arquivo de workflow é atualizado

**Ambiente:**
- Executa em `ubuntu-latest`
- Usa Python 3.10
- Detecta automaticamente ambiente CI para configurações conservadoras

#### Etapas do Workflow

1. **Configuração do Repositório**
   ```yaml
   - Checkout do repositório com permissões de escrita
   - Configuração do ambiente Python 3.10
   - Instalação de dependências do requirements.txt
   ```

2. **Scraping de Eventos**
   ```yaml
   - Execução do scrape_hacktown.py com otimizações CI
   - Gerenciamento do diretório de saída
   - Processamento de todas as datas de eventos do HackTown 2025
   ```

3. **Gerenciamento de Cache**
   ```yaml
   - Geração de versão de cache busting baseada em timestamp
   - Atualização do index.html com novos números de versão
   - Garantia de que o PWA atualiza adequadamente nos navegadores
   ```

4. **Operações Git**
   ```yaml
   - Verificação de mudanças em events/ e index.html
   - Commit de mudanças com timestamp
   - Push de atualizações de volta ao repositório
   ```

#### Funcionalidades do Workflow

- **Atualizações Inteligentes**: Só faz commit quando mudanças reais são detectadas
- **Cache Busting**: Atualiza automaticamente versões de cache do PWA
- **Tratamento de Erros**: Tratamento gracioso de arquivos e diretórios ausentes
- **Otimização CI**: Usa configurações conservadoras de Scraping no GitHub Actions
- **Timestamps Automatizados**: Commits incluem timestamp de execução

#### Monitoramento do Workflow

**Aba GitHub Actions:**
- Visualizar execuções do workflow e seus status
- Verificar logs para progresso de Scraping e erros
- Monitorar tempo de execução e taxas de sucesso

**Atualizações do Repositório:**
- Commits automáticos aparecem com mensagens "Update event data"
- Arquivos de eventos são atualizados no diretório `events/`
- Versões de cache PWA são automaticamente incrementadas

#### Execução Manual

Você pode acionar manualmente o workflow:

1. Vá para a aba **Actions** do seu repositório
2. Selecione o workflow **"Scrape Hacktown Events"**
3. Clique no botão **"Run workflow"**
4. Escolha a branch (geralmente `main`)
5. Clique em **"Run workflow"** para executar

#### Solução de Problemas do Workflow

**Problemas Comuns:**
- **Erros de Permissão**: Certifique-se de que o repositório tem Actions habilitadas
- **Rate Limiting**: Workflow usa configurações otimizadas para CI para evitar limites de API
- **Falhas de Commit**: Verifique se as regras de proteção do repositório permitem que Actions façam push

**Passos de Debug:**
1. Verifique a aba Actions para logs detalhados
2. Procure por mensagens de erro na etapa "Run scraper"
3. Verifique se o diretório events contém arquivos atualizados
4. Confirme se as versões de cache estão sendo atualizadas no index.html

### Suporte CI/CD
O raspador inclui otimizações para CI/CD:
- Detecta ambientes CI (variáveis `CI` ou `GITHUB_ACTIONS`)
- Ajusta configurações de concorrência e retry automaticamente
- Rate limiting conservador em ambientes automatizados

### Opções Alternativas de Agendamento
Considere configurar execuções automatizadas usando:
- **GitHub Actions**: ✅ Já configurado (recomendado)
- **Cron Jobs**: Para agendamento baseado em servidor
- **Cloud Functions**: Para automação serverless
- **AWS Lambda**: Scraping orientada por eventos

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

## 🚀 Deploy

### Hospedagem Estática
Faça deploy em qualquer serviço de hospedagem estática:
- **GitHub Pages**: Deploy automático do repositório

### Scraping Automatizada
Configure Scraping agendada usando:
- **GitHub Actions**: `.github/workflows/scrape-events.yml`

## 📱 Funcionalidades PWA

- **Instalável**: Adicionar à tela inicial em dispositivos móveis
- **Suporte Offline**: Eventos em cache disponíveis sem internet
- **Experiência Similar a App**: Modo tela cheia e sensação nativa
- **Carregamento Rápido**: Estratégias de cache do service worker
- **Responsivo**: Funciona em desktop, tablet e mobile

## 🤝 Contribuindo

1. Faça fork do repositório
2. Crie uma branch de feature (`git checkout -b feature/funcionalidade-incrivel`)
3. Commit suas mudanças (`git commit -m 'Adiciona funcionalidade incrível'`)
4. Push para a branch (`git push origin feature/funcionalidade-incrivel`)
5. Abra um Pull Request

---

**Feito com ❤️ para a comunidade HackTown 2025 com a assistência do Amazon Q**
