import json,logging,os,re
from dotenv import load_dotenv
load_dotenv()
log=logging.getLogger(__name__)
class AIServiceError(Exception): pass
def generate_text(prompt):
 if os.getenv("MOCK_AI","false").lower()=="true": raise AIServiceError("Mock mode enabled")
 key=os.getenv("GROQ_API_KEY","").strip()
 if not key: raise AIServiceError("AI recommendations are not configured. Add a Groq API key or enable mock mode.")
 try:
  from groq import Groq
  c=Groq(api_key=key,timeout=45,max_retries=2)
  r=c.chat.completions.create(model=os.getenv("GROQ_MODEL","openai/gpt-oss-120b"),messages=[{"role":"system","content":"You are PocketSmart AI, a budget planning assistant. Return only valid JSON without markdown."},{"role":"user","content":prompt}],response_format={"type":"json_object"},temperature=.4)
  return r.choices[0].message.content or ""
 except Exception as e:
  log.exception("Groq request failed")
  raise AIServiceError("PocketSmart AI couldn't generate recommendations right now. Please try again.") from e
def generate_structured_response(prompt):
 raw=generate_text(prompt)
 try:return json.loads(raw)
 except json.JSONDecodeError:
  m=re.search(r"\{[\s\S]*\}",raw)
  if m:
   try:return json.loads(m.group())
   except json.JSONDecodeError:pass
  log.error("Groq returned malformed JSON")
  raise AIServiceError("PocketSmart AI returned an unusable plan. Please try again.")

