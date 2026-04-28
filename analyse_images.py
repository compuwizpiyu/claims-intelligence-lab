import os, json
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from openai import AzureOpenAI
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

load_dotenv()
mongo = MongoClient(os.getenv("MONGODB_URI"))
db = mongo[os.getenv("MONGODB_DATABASE")]
oai = AzureOpenAI(azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"), api_version="2024-06-01")
vision = ImageAnalysisClient(endpoint=os.getenv("AZURE_VISION_ENDPOINT"),
    credential=AzureKeyCredential(os.getenv("AZURE_VISION_API_KEY")))

PROMPT = """Extract from this receipt OCR text as JSON:
{"date":"YYYY-MM-DD","vendor_name":"","vendor_location":"",
"category":"Breakfast|Lunch|Dinner|Snacks|Water|Taxi|Other",
"items":[],"subtotal":0,"tax":0,"tip":0,"total":0,
"currency":"USD","payment_method":""}
Null for unknowns. ONLY valid JSON.\n\nOCR:\n"""

def process(path):
    name = os.path.basename(path)
    if db["extracted_fields"].find_one({"source_file":name}): return
    print(f"  {name}")
    with open(path,"rb") as f:
        r = vision.analyze(image_data=f.read(), visual_features=[VisualFeatures.READ])
    ocr = "\n".join(l.text for b in (r.read.blocks or []) for l in b.lines).strip()
    if not ocr: return
    db["images"].insert_one({"filename":name,"ocr_text":ocr,"processed_at":datetime.utcnow()})
    resp = oai.chat.completions.create(model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        messages=[{"role":"system","content":"Extract structured data from receipts."},
                  {"role":"user","content":PROMPT+ocr}], temperature=0, max_tokens=500)
    raw = resp.choices[0].message.content.strip()
    try: fields = json.loads(raw)
    except: fields = json.loads(raw.split("```json")[-1].split("```")[0].strip())
    fields["source_file"]=name; fields["extracted_at"]=datetime.utcnow().isoformat()
    db["extracted_fields"].insert_one(fields)
    print(f"  -> {fields.get('vendor_name','?')} ${fields.get('total',0)}")

if __name__=="__main__":
    d="data/claims"
    imgs=[f for f in os.listdir(d) if f.lower().endswith((".jpeg",".jpg",".png"))]
    print(f"Found {len(imgs)} images\n")
    for i in sorted(imgs): process(os.path.join(d,i))
    print(f"\nExtracted: {db['extracted_fields'].count_documents({})}")