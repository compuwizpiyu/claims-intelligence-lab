import os, json, azure.functions as func
from openai import AzureOpenAI

app = func.FunctionApp()
client = AzureOpenAI(azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"), api_version="2024-06-01")

@app.route(route="embeddings", methods=["POST"])
def generate_embeddings(req: func.HttpRequest) -> func.HttpResponse:
    body = req.get_json()
    text = body.get("input","")
    if not text: return func.HttpResponse('{"error":"input required"}', status_code=400)
    emb = client.embeddings.create(input=text,
        model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT","text-embedding-3-small"))
    return func.HttpResponse(json.dumps({"embedding":emb.data[0].embedding}),
        mimetype="application/json")