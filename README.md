# Claims Intelligence Lab — MongoDB Atlas + Microsoft Foundry

> **Hands-on lab**: Build an AI-powered claims document extraction and image analysis system using MongoDB Atlas (vector search), Microsoft Foundry (agents), and Azure AI Vision.
>
> This lab demonstrates **two integration paths** — pick the one that fits your use case, or try both.

---

## Two integration paths

| | Path A — Chat Playground (Classic UI only) | Path B — Foundry Agents + MCP Server |
|---|---|---|
| **What it is** | Point-and-click RAG in the classic Foundry chat playground. Select MongoDB Atlas as a data source, connect your vector index, and chat immediately. **Does not work in New Foundry UI.** | Deploy the MongoDB MCP Server on Azure Container Apps. Create a Foundry Agent that calls MongoDB via MCP for find, aggregate, vector search, and CRUD. |
| **Best for** | Quick demos, prototyping RAG, testing LLM + data combos | Autonomous agents that query, write, and act on live data |
| **Complexity** | Low — no code, wizard-based | Medium — Container Apps deployment + agent config |
| **Capabilities** | Read-only vector search grounded chat | Full DB operations: find, aggregate, vector search, insert, update |
| **UI requirement** | **Classic Foundry UI only** (not New Foundry) | Works with **New Foundry UI** |
| **Lab parts** | Parts 1–5, then **Part 6A** | Parts 1–5, then **Parts 6B–8B** |

> **Terminology**: This lab uses the new **Microsoft Foundry** portal at [ai.azure.com](https://ai.azure.com) — not the older "Azure AI Studio (classic)".

---

## Table of contents

- [Architecture overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Part 1 — Provision MongoDB Atlas from Azure Marketplace](#part-1--provision-mongodb-atlas-from-azure-marketplace)
- [Part 2 — Create a MongoDB Atlas cluster and database](#part-2--create-a-mongodb-atlas-cluster-and-database)
- [Part 3 — Provision Azure AI services](#part-3--provision-azure-ai-services)
- [Part 4 — Ingest claims documents into MongoDB vector store](#part-4--ingest-claims-documents-into-mongodb-vector-store)
- [Part 5 — Build an image analysis pipeline](#part-5--build-an-image-analysis-pipeline)
- **Path A** *(Classic UI only)*: [Part 6A — Chat with your data in Foundry Playground](#part-6a--chat-with-your-data-in-foundry-playground)
- **Path B**: [Part 6B — Deploy MongoDB MCP Server](#part-6b--deploy-mongodb-mcp-server-on-azure-container-apps) | [Part 7B — Embedding endpoint](#part-7b--deploy-an-embedding-endpoint) | [Part 8B — Create and test agents](#part-8b--create-and-test-agents-in-microsoft-foundry)
- [Bonus — Local CLI agent](#bonus--local-cli-agent)
- [Cleanup](#cleanup) | [Troubleshooting](#troubleshooting) | [References](#references)

---

## Architecture overview

### Path A — Chat Playground with MongoDB Atlas

```
User  --->  Microsoft Foundry Chat Playground
                  |
                  |  "Add your data" -> MongoDB Atlas
                  |
            ┌─────▼──────┐        ┌────────────────────┐
            │   GPT-4o   │ <----> │  MongoDB Atlas      │
            │             │        │  Vector Search      │
            └─────────────┘        │  (claims_db)        │
                                   └────────────────────┘
```

No code. No containers. Wizard-based. Read-only vector search RAG.

### Path B — Foundry Agents + MongoDB MCP Server

```
User  --->  Microsoft Foundry Agent
                  |
                  |  MCP tool call (HTTPS)
                  ▼
            ┌─────────────────────┐
            │ Azure Container Apps │
            │ ┌─────────────────┐ │
            │ │ MongoDB MCP     │ │
            │ │ Server          │ │
            │ └────────┬────────┘ │
            └──────────┼──────────┘
                       │  mongodb+srv://
                       ▼
            ┌────────────────────┐
            │ MongoDB Atlas      │
            │ find, aggregate,   │
            │ vector search,     │
            │ insert, update     │
            └────────────────────┘
```

Full read/write. Agent calls MCP Server over HTTPS. MCP Server translates to MongoDB operations.

---

## Prerequisites

| Requirement | Details |
|---|---|
| Azure subscription | Pay-as-you-go or MSDN |
| Azure CLI | v2.55+ |
| Python 3.10+ | With pip |
| Git | For cloning |

```bash
git clone https://github.com/<your-org>/claims-intelligence-lab.git
cd claims-intelligence-lab
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**requirements.txt**:
```
pymongo==4.7.3
openai==1.35.0
azure-ai-vision-imageanalysis==1.0.0
azure-identity==1.17.1
python-dotenv==1.0.1
pypdf==4.3.1
Pillow==10.4.0
requests==2.32.3
azure-functions==1.24.0
```

> **Note**: `azure-functions` is only needed if you are deploying the embedding endpoint (Part 7B).

---

## Part 1 — Provision MongoDB Atlas from Azure Marketplace

1. Sign in to [Azure Portal](https://portal.azure.com)
2. Search **"MongoDB Atlas"** → Marketplace → **MongoDB Atlas on Azure — Pay As You Go**
3. Click **Create**:
   - Resource group: `rg-claimnsdemo` (create new or use existing)
   - Resource name: choose a name (e.g. `claims-lab-mongodb`)
   - Region: **East US**

> **Actual value used in this lab**: Resource group = `rg-claimnsdemo`
4. **Review + create** → **Create**
5. Once deployed → **Go to resource** → **Open MongoDB Atlas**
6. Accept terms. Billing flows through your Azure subscription.

---

## Part 2 — Create a MongoDB Atlas cluster and database

### 2.1 — Free-tier cluster

In Atlas → **Build a Database** → **M0 (Free)**, Provider **Azure**, Region **eastus**, Name your cluster → **Create Deployment**

> **Actual value used in this lab**: Cluster host = `cluster-claimsdemo.b70ssff.mongodb.net`

### 2.2 — Access

- Create user with a strong password (**save it**)
- Network Access: add your IP. For lab: `0.0.0.0/0`

> **Tip**: Save your username and password — you'll need them for the connection string.

### 2.3 — Connection string

Click **Connect** → Drivers → Python. Copy:
```
mongodb+srv://<username>:<password>@<cluster-host>.mongodb.net/
```

> Replace `<username>`, `<password>`, and `<cluster-host>` with your actual values.

### 2.4 — Database and collections

Browse Collections → Create Database `claims_db` with collections: `documents`, `extracted_fields`, `images`

### 2.5 — Vector Search index

Atlas Search → Create Search Index → JSON Editor → database `claims_db`, collection `documents`, index name `vector_index`:

```json
{
  "fields": [
    {"type": "vector", "path": "embedding", "numDimensions": 1536, "similarity": "cosine"},
    {"type": "filter", "path": "category"},
    {"type": "filter", "path": "date"}
  ]
}
```

Wait for **Active** status.

---

## Part 3 — Provision Azure AI services

### 3.1 — Azure OpenAI

```bash
az login

az cognitiveservices account create \
  --name <your-openai-resource> --resource-group rg-claimnsdemo \
  --kind OpenAI --sku S0 --location eastus --yes

az cognitiveservices account deployment create \
  --name <your-openai-resource> --resource-group rg-claimnsdemo \
  --deployment-name gpt-4o --model-name gpt-4o \
  --model-version "2024-08-06" --model-format OpenAI \
  --sku-capacity 30 --sku-name Standard

az cognitiveservices account deployment create \
  --name <your-openai-resource> --resource-group rg-claimnsdemo \
  --deployment-name text-embedding-3-small --model-name text-embedding-3-small \
  --model-version "1" --model-format OpenAI \
  --sku-capacity 30 --sku-name Standard
```

> **Actual value used in this lab**: OpenAI resource = `aicu-claimnsdemorbm2e`

Get endpoint and key:
```bash
az cognitiveservices account show --name <your-openai-resource> \
  --resource-group rg-claimnsdemo --query properties.endpoint -o tsv
az cognitiveservices account keys list --name <your-openai-resource> \
  --resource-group rg-claimnsdemo --query key1 -o tsv
```

> **⚠️ Important — API Key Authentication**: If you get a `403 Key based authentication is disabled` error, API key auth may be turned off on your OpenAI resource. Re-enable it with:
> ```bash
> az cognitiveservices account update \
>   --name <your-openai-resource> --resource-group rg-claimnsdemo \
>   --set properties.disableLocalAuth=false
> ```

### 3.2 — Azure AI Vision

```bash
az cognitiveservices account create \
  --name <your-vision-resource> --resource-group rg-claimnsdemo \
  --kind ComputerVision --sku S1 --location eastus --yes
```

> **Actual value used in this lab**: Vision resource = `mongodbazureaiservices`

### 3.3 — Microsoft Foundry project

1. Go to [ai.azure.com](https://ai.azure.com) → **Create project**
2. Project name: choose a name, Hub: choose or create, RG: `rg-claimnsdemo`, Region: East US
3. **Management** → **Connected resources**:
   - New connection → Azure OpenAI → your OpenAI resource
   - New connection → Azure AI Vision → your Vision resource

> **Actual value used in this lab**: Foundry project = `proj-mongoDBDemo`

### 3.4 — Environment file

Create `.env`:
```env
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster-host>.mongodb.net/
MONGODB_DATABASE=claims_db
AZURE_OPENAI_ENDPOINT=https://<your-openai-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_VISION_ENDPOINT=https://<your-vision-resource>.cognitiveservices.azure.com/
AZURE_VISION_API_KEY=<key>
```

> **⚠️ Important**: Do NOT wrap values in quotes in the `.env` file — `python-dotenv` includes literal quote characters if you do. Use bare values only.
>
> See `.env.example` for the template. Copy it to `.env` and fill in your values:
> ```bash
> cp .env.example .env
> ```

---

## Part 4 — Ingest claims documents into MongoDB vector store

The ingestion script is included in this folder as **`docIngestion.py`**. It reads PDFs from `data/claims/`, chunks the text, generates embeddings via Azure OpenAI, and inserts them into the `documents` collection in MongoDB Atlas.

**What it does**:
- Reads all `.pdf` files from `data/claims/`
- Splits text into 500-char chunks with 100-char overlap
- Generates embeddings using `text-embedding-3-small`
- Inserts chunks with embeddings into `claims_db.documents`
- Skips files already ingested (dedup by MD5 hash)

```bash
mkdir -p data/claims   # place your PDFs here
python docIngestion.py
```

> **Actual result in this lab**: 7 PDFs → 19 chunks inserted into `claims_db.documents`.

Verify: Atlas → Browse Collections → `claims_db.documents` → confirm `embedding` arrays. Atlas Search → `vector_index` Active.

---

## Part 5 — Build an image analysis pipeline

The image analysis script is included in this folder as **`analyse_images.py`**. It processes receipt images using Azure AI Vision OCR and GPT-4o to extract structured data.

**What it does**:
- Reads all `.jpeg`, `.jpg`, `.png` files from `data/claims/`
- Runs Azure AI Vision OCR to extract text from each image
- Sends OCR text to GPT-4o to extract structured fields (vendor, total, category, items, etc.)
- Stores raw OCR text in `claims_db.images`
- Stores structured JSON in `claims_db.extracted_fields`
- Skips images already processed (dedup by source filename)

```bash
python analyse_images.py
```

> **Actual result in this lab**: 4 receipt images processed — a paolo GASTRONOMIA ($59.40), Coffee Club ($129.13), Cinnabon ($15.10), Comfort Transportation ($9.00).

---

## Path A

## Part 6A — Chat with your data in Foundry Playground

> **⚠️ Does NOT work in New Foundry UI**: The "Add your data" feature in the Chat Playground does **not** list **MongoDB Atlas** as a data source in the New Foundry UI at [ai.azure.com](https://ai.azure.com). This path **only works in the classic (old) Azure AI Studio UI**. If you are using the New Foundry UI (which is now the default), **skip to Path B** (Parts 6B–8B).
>
> To try Path A, you would need to switch back to the classic Azure AI Studio experience, which may no longer be available.

If using classic Foundry UI where MongoDB Atlas is available in the data-source dropdown:

1. **Playgrounds** → **Chat** → select `gpt-4o`
2. **Add your data** → **MongoDB Atlas** → fill in cluster endpoint, `claims_db`, collection `documents`, index `vector_index`, embedding deployment `text-embedding-3-small`
3. Chat — queries are auto-embedded, searched via Atlas vector index, and answered with citations

**Limitation**: Read-only vector search only. No aggregations, no writes. For full capabilities, use Path B.

> **Recommendation**: Use **Path B** — it works with the current New Foundry UI, supports full database operations, and was successfully tested end-to-end in this lab.

---

## Path B

## Part 6B — Deploy MongoDB MCP Server on Azure Container Apps

The MongoDB MCP Server is an open-source container that implements the Model Context Protocol. It bridges Microsoft Foundry agents and MongoDB Atlas. Agents call it over HTTPS, and it translates into MongoDB operations (find, aggregate, vector search, insert, etc.).

> **Why not direct function calling?** Foundry agents cannot execute arbitrary code server-side. They call external tools via the MCP protocol. The MongoDB MCP Server is listed in the Foundry Tools Catalog.

### 6B.1 — Clone and configure

```bash
git clone https://github.com/mongodb-js/mongodb-mcp-server.git
cd mongodb-mcp-server/deploy/azure
```

Edit `bicep/params.json` — set your Atlas connection string:

```json
{
  "parameters": {
    "location": {"value": "eastus"},
    "containerAppName": {"value": "claims-mcp-server"},
    "mdbConnectionString": {
      "value": "mongodb+srv://<username>:<password>@<cluster-host>.mongodb.net/"
    }
  }
}
```

> **Note**: The Bicep template parameter is `mdbConnectionString` (not `mongodbAtlasConnectionString`). You can omit `containerImage` to use the template default.
>
> Replace with your actual MongoDB Atlas connection string from Part 2.3.

### 6B.2 — Deploy

```bash
az deployment group create \
  --resource-group rg-claimnsdemo \
  --template-file bicep/main.bicep \
  --parameters @bicep/params.json
```

> **⚠️ ghcr.io access**: If deploying from Azure Portal fails with `DENIED` for the container image, deploy via **Cloud Shell** instead using the commands above.

### 6B.3 — Get the URL

```bash
az containerapp show --name claims-mcp-server \
  --resource-group rg-claimnsdemo \
  --query properties.configuration.ingress.fqdn -o tsv
```

Result: `claims-mcp-server.<id>.eastus.azurecontainerapps.io`

> **⚠️ Important**: The full MCP endpoint URL must include the `/mcp` path. When configuring tools in Foundry, use:
> ```
> https://claims-mcp-server.<id>.eastus.azurecontainerapps.io/mcp
> ```
> Using the root URL without `/mcp` will return HTTP 404.
>
> Save this URL — you'll use it in Part 8B when configuring the agent's MCP tool.

---

## Part 7B — Deploy an embedding endpoint

For vector search via agents, deploy an Azure Function that generates embeddings:

The Azure Function code is included in this folder as **`function_app.py`**. It exposes a `POST /api/embeddings` endpoint that accepts `{"input": "text"}` and returns `{"embedding": [...]}`.

Deploy:

> **Prerequisite**: You need a storage account first. Create one if you don't have it:
> ```bash
> az storage account create --name claimslabstore2025 \
>   --resource-group rg-claimnsdemo --location eastus --sku Standard_LRS
> ```

```bash
az functionapp create --name claims-lab-embeddings \
  --resource-group rg-claimnsdemo --consumption-plan-location eastus \
  --runtime python --runtime-version 3.11 --functions-version 4 \
  --storage-account claimslabstore2025 --os-type linux

az functionapp config appsettings set --name claims-lab-embeddings \
  --resource-group rg-claimnsdemo --settings \
  AZURE_OPENAI_ENDPOINT=<your-openai-endpoint> \
  AZURE_OPENAI_API_KEY=<your-key> \
  AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

func azure functionapp publish claims-lab-embeddings --python
```

> **Important**: The `--python` flag is required for `func azure functionapp publish`. Also ensure a `host.json` file exists in your function directory:
> ```json
> {
>   "version": "2.0",
>   "extensionBundle": {
>     "id": "Microsoft.Azure.Functions.ExtensionBundle",
>     "version": "[4.*, 5.0.0)"
>   }
> }
> ```

OpenAPI spec (used in Part 8B):
```yaml
openapi: 3.0.1
info:
  title: Embedding Service API
  version: "1.0"
paths:
  /api/embeddings:
    post:
      summary: Generate embeddings
      operationId: generateEmbeddings
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                input:
                  type: string
      responses:
        '200':
          description: Vector
          content:
            application/json:
              schema:
                type: object
                properties:
                  embedding:
                    type: array
                    items:
                      type: number
```

---

## Part 8B — Create and test agents in Microsoft Foundry

### 8B.1 — Create the Claims Agent

1. [ai.azure.com](https://ai.azure.com) → your project → **Agents** → **New agent**
2. Name: `claims-extraction-agent`, Model: **`gpt-4.1`** (recommended — see note below)
3. Instructions:

> **⚠️ Model choice matters**: `gpt-4o` may fail to properly invoke MCP tools or return empty responses even when data exists. Switching to **`gpt-4.1`** resolved this in testing. If `gpt-4.1` is not available in your deployment, create a new deployment for it first (Part 3.1 pattern).

```
You are a claims processing assistant with MongoDB Atlas access via MCP tools.

CRITICAL: The database name is exactly "claims_db". Always use "claims_db" as the database parameter in every MCP tool call. Never guess or invent database names.

Available collections in claims_db:
- "documents" — PDF text chunks with embeddings (fields: filename, text, embedding, chunk_index, source_type)
- "extracted_fields" — structured receipt data (fields: date, vendor_name, vendor_location, category, items, subtotal, tax, tip, total, currency, source_file)
- "images" — raw OCR text from receipts (fields: filename, ocr_text)

Workflow:
1. ALWAYS start by calling listCollections on database "claims_db" to confirm connectivity
2. For summaries or totals, use aggregate on "extracted_fields" with $group
3. For finding specific claims, use find on "extracted_fields" with a filter
4. For text/semantic queries about PDF content, use find on "documents"
5. Always pass database="claims_db" and the correct collection name

Rules:
- Cite source filenames. Format amounts as USD. Group by category in summaries.
- If a tool call returns empty results, try a different collection or a broader filter.
```

> **⚠️ Why so explicit?** Without detailed instructions, the LLM will guess database names (e.g. "claims_database") and collection names, causing empty results even though your data is there. The more specific the instructions, the more reliably the agent uses MCP tools.

### 8B.2 — Add MongoDB MCP Server tool

1. **Tools** → search for **MongoDB MCP Server** in the Tools Catalog → **Connect**
2. Or: **Add a tool** → **MCP** → paste your Container Apps URL from Part 6B
3. **⚠️ The URL must end with `/mcp`** — e.g. `https://claims-mcp-server.<id>.eastus.azurecontainerapps.io/mcp`
4. Enable tools: `find`, `aggregate`, `count`, `listCollections`
5. Save

> **Common error**: If you use the root URL without `/mcp`, you will get `HTTP 404 (Not Found) while enumerating tools`.

### 8B.3 — Add embedding OpenAPI tool

1. **Tools** → **Add a tool** → **OpenAPI**
2. Paste the spec from Part 7B. Server URL: `https://claims-lab-embeddings.azurewebsites.net`
3. Save

### 8B.4 — Create Image Analysis Agent

1. **New agent**: `image-analysis-agent`, Model: `gpt-4o`
2. Instructions: "You analyse receipt images. Extract date, vendor, items, total, category. Flag anomalies."
3. Enable **Code interpreter** under Tools
4. Save

### 8B.5 — Test

Select `claims-extraction-agent` → **Try in playground**:

- `Give me a summary of all claims by category`
- `Find all taxi rides from March 2025`
- `What claims were at Grant Park Bistro?`
- `How much was spent on food in November?`

For images: select `image-analysis-agent` → upload receipt → "Extract details from this receipt"

### 8B.6 — Deploy as API (optional)

Agent → **Deploy** → endpoint name `claims-agent-endpoint` → Serverless → Deploy

```bash
curl -X POST "https://<endpoint>.inference.ai.azure.com/chat/completions" \
  -H "Authorization: Bearer <key>" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Summarise all claims"}]}'
```

---

## Bonus — Local CLI agent

For testing without Foundry, you can create a local CLI agent script. This script uses Azure OpenAI function calling with three tools: `search_claims` (vector search), `get_summary` (aggregate by category), and `by_category` (filter by category). It connects directly to MongoDB Atlas using the same `.env` file.

> This script is not included in the folder — see the [README_ORIGINAL.md](README_ORIGINAL.md) for the full source code if you want to create it.

---

## Cleanup

```bash
az group delete --name rg-claimnsdemo --yes --no-wait
# Atlas portal: cluster -> Terminate
```

---

## Troubleshooting

| Issue | Solution |
|---|---|
| MongoDB connection timeout | Atlas → Network Access → add your IP or `0.0.0.0/0` |
| OpenAI 403 "Key based auth disabled" | `az cognitiveservices account update --name <resource> --resource-group rg-claimnsdemo --set properties.disableLocalAuth=false` |
| OpenAI quota exceeded | Azure Portal → OpenAI resource → Quotas → increase TPM |
| Vector search empty | Verify `vector_index` Active. Check 1536 dimensions. |
| Vision OCR empty | Image under 20MB, legible, try PNG format |
| `.env` values not loading correctly | Do NOT wrap values in quotes — `python-dotenv` keeps literal quote chars |
| ghcr.io DENIED when deploying MCP container | Deploy via Cloud Shell (`az deployment group create`) instead of Portal |
| MCP Server HTTP 404 | URL must end with `/mcp` — e.g. `https://<app>.azurecontainerapps.io/mcp` |
| MCP Server HTTP 403 | `MDB_MCP_CONNECTION_STRING` env var is empty — set it via `az containerapp update` |
| MCP Server returns 400 on curl | This is **expected** — the MCP server only responds to MCP protocol requests, not plain HTTP |
| Shell eats `$` in connection string | Wrap the value in single quotes when using `az containerapp update --set-env-vars` |
| Agent queries wrong database name | Instructions must explicitly say `database: claims_db` — LLMs invent names like "claims_database" |
| Agent connects to MCP but can't answer queries | Switch model from `gpt-4o` to **`gpt-4.1`** — gpt-4o may not invoke MCP tools correctly |
| MongoDB not in playground dropdown | New Foundry UI doesn't support MongoDB Atlas in Chat Playground yet — use Path B (Agents + MCP) |
| `func azure functionapp publish` fails | Needs `host.json` in the function directory and `--python` flag |
| See "classic" AI Studio UI | Use ai.azure.com (not legacy Azure AI Studio URL) |

---

## Project structure

```
MongodbLabs_docIngestion/
├── README.md                # This file
├── README_ORIGINAL.md       # Original README backup (with full inline code)
├── requirements.txt
├── .env                     # Environment variables (do not commit)
├── docIngestion.py          # Part 4 — PDF ingestion + vector embeddings
├── analyse_images.py        # Part 5 — Receipt image OCR + structured extraction
├── function_app.py          # Part 7B — Azure Function embedding endpoint
└── data/
    └── claims/              # Your PDFs and receipt images
```

---

## References

- [Connect Foundry Agents to MongoDB Atlas (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/partner-solutions/mongo-db/connect-foundry-agents)
- [MongoDB MCP Server (GitHub)](https://github.com/mongodb-js/mongodb-mcp-server)
- [MCP Server Azure deployment (Bicep)](https://github.com/mongodb-js/mongodb-mcp-server/blob/main/deploy/azure/README.md)
- [RAG with MongoDB Atlas + Azure OpenAI (MongoDB blog)](https://www.mongodb.com/company/blog/technical/rag-made-easy-mongodb-atlas-azure-openai)
- [MongoDB + Foundry integration announcement (MongoDB blog)](https://www.mongodb.com/company/blog/innovation/building-next-gen-ai-agents-mongodb-atlas-integration-microsoft-foundry)
- [Azure OpenAI on your MongoDB data (API ref)](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/references/mongo-db)
- [MongoDB Atlas on Azure Marketplace](https://www.mongodb.com/cloud/atlas/azure)
- [Atlas Vector Search docs](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/)
- [Microsoft Foundry docs](https://learn.microsoft.com/en-us/azure/ai-studio/)
- [Azure AI Vision](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-image-analysis)

---

*This lab is provided for educational purposes. See [LICENSE](LICENSE) for details.*
