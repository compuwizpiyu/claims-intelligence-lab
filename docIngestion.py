import os, hashlib
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from openai import AzureOpenAI
from pypdf import PdfReader

load_dotenv()
mongo = MongoClient(os.getenv("MONGODB_URI"))
db = mongo[os.getenv("MONGODB_DATABASE")]
docs = db["documents"]
oai = AzureOpenAI(azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"), api_version="2024-06-01")
EMB = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

def chunk(text, size=500, overlap=100):
    chunks, s = [], 0
    while s < len(text):
        chunks.append(text[s:s+size]); s += size - overlap
    return chunks

def ingest(path):
    name = os.path.basename(path)
    fh = hashlib.md5(open(path,"rb").read()).hexdigest()
    if docs.find_one({"file_hash": fh}): print(f"  Skip {name}"); return
    print(f"  Processing: {name}")
    text = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages).strip()
    if not text: return
    cks = chunk(text)
    recs = [{"filename":name,"file_hash":fh,"chunk_index":i,"text":c,
             "embedding":oai.embeddings.create(input=c,model=EMB).data[0].embedding,
             "ingested_at":datetime.utcnow(),"source_type":"pdf"} for i,c in enumerate(cks)]
    docs.insert_many(recs)
    print(f"  -> {len(recs)} chunks inserted")

if __name__=="__main__":
    d="data/claims"
    fs=[f for f in os.listdir(d) if f.endswith(".pdf")]
    print(f"Found {len(fs)} PDFs\n")
    for f in sorted(fs): ingest(os.path.join(d,f))
    print(f"\nTotal chunks: {docs.count_documents({})}")