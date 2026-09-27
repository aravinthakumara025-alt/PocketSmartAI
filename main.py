import os, json, logging, secrets, hashlib, hmac
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import jwt
from database import Base, engine, get_db
from models import User, Recommendation
from services.home_service import generate_home_plan
from services.party_service import generate_party_plan
from services.jewelry_service import generate_jewelry_plan
from services.groq_service import AIServiceError

load_dotenv()
logging.basicConfig(level=logging.INFO)
log=logging.getLogger("pocketsmart")
ROOT=Path(__file__).parent
UPLOAD=Path(os.getenv("UPLOAD_DIR", str(ROOT/"uploads")))
SECRET=os.getenv("SECRET_KEY", "dev-only-change-me")
ALG=os.getenv("ALGORITHM","HS256")
EXPIRE=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES","60"))
app=FastAPI(title="PocketSmart AI", description="Your Smart Budget & Recommendation Assistant")
app.mount("/static",StaticFiles(directory=ROOT/"static"),name="static")
templates=Jinja2Templates(directory=ROOT/"templates")

@app.on_event("startup")
def startup():
 if os.getenv("APP_ENV","development").lower()=="production":
  if SECRET=="dev-only-change-me" or len(SECRET)<32:raise RuntimeError("Production requires a strong SECRET_KEY.")
  if os.getenv("MOCK_AI","false").lower()!="true" and not os.getenv("GROQ_API_KEY"):raise RuntimeError("Production requires GROQ_API_KEY when MOCK_AI is disabled.")
  if os.getenv("COOKIE_SECURE","false").lower()!="true":raise RuntimeError("Production requires COOKIE_SECURE=true behind HTTPS.")
 UPLOAD.mkdir(parents=True,exist_ok=True);Base.metadata.create_all(bind=engine)
 log.info("PocketSmart AI starting... Database: OK | Templates: OK | Static files: OK | Groq configuration: %s | Mock AI: %s","OK" if os.getenv("GROQ_API_KEY") else "NOT CONFIGURED",os.getenv("MOCK_AI","false"))
def hash_password(p):
 salt=secrets.token_bytes(16);derived=hashlib.scrypt(p.encode(),salt=salt,n=2**14,r=8,p=1)
 return salt.hex()+":"+derived.hex()
def verify_password(p,stored):
 try:
  salt_hex,digest=stored.split(":");return hmac.compare_digest(hashlib.scrypt(p.encode(),salt=bytes.fromhex(salt_hex),n=2**14,r=8,p=1).hex(),digest)
 except Exception:return False
def token_for(user):return jwt.encode({"sub":str(user.id),"exp":datetime.now(timezone.utc)+timedelta(minutes=EXPIRE)},SECRET,algorithm=ALG)
def current_user(request:Request,db:Session):
 token=request.cookies.get("access_token")
 if not token:return None
 try:
  uid=jwt.decode(token,SECRET,algorithms=[ALG]).get("sub")
  return db.get(User,int(uid)) if uid else None
 except Exception:return None
def page(request,name,db,**context):
 return templates.TemplateResponse(request=request,name=name,context={"request":request,"user":current_user(request,db),**context})
def auth_required(request,db):
 u=current_user(request,db)
 if not u:raise HTTPException(303,headers={"Location":"/login"})
 return u

def error_response(request,db,status,message):return templates.TemplateResponse(request=request,name="error.html",context={"request":request,"user":current_user(request,db),"status":status,"message":message},status_code=status)
@app.exception_handler(404)
async def not_found(request,exc):
 with next(get_db()) as db:return error_response(request,db,404,"We couldn't find that page.")
@app.exception_handler(405)
async def method_not_allowed(request,exc):
 with next(get_db()) as db:return error_response(request,db,405,"That action is not available here.")
@app.exception_handler(422)
async def invalid_request(request,exc):
 with next(get_db()) as db:return error_response(request,db,422,"Please check the information you entered and try again.")
@app.exception_handler(500)
async def server_error(request,exc):
 log.exception("Unhandled server error")
 with next(get_db()) as db:return error_response(request,db,500,"Something went wrong. Please try again.")

@app.get("/",response_class=HTMLResponse)
def home(request:Request,db:Session=Depends(get_db)):return page(request,"index.html",db)
@app.get("/register",response_class=HTMLResponse)
def register_page(request:Request,db:Session=Depends(get_db)):return page(request,"auth.html",db,mode="register")
@app.post("/register")
def register(request:Request,username:str=Form(...),email:str=Form(...),password:str=Form(...),confirm_password:str=Form(...),db:Session=Depends(get_db)):
 username=username.strip();email=email.strip().lower()
 if len(username)<3 or len(username)>40 or not all(c.isalnum() or c in "_-" for c in username):return page(request,"auth.html",db,mode="register",error="Username must be 3–40 letters, numbers, _ or -.")
 if "@" not in email or len(email)>255:return page(request,"auth.html",db,mode="register",error="Enter a valid email address.")
 if len(password)<8:return page(request,"auth.html",db,mode="register",error="Use a password with at least 8 characters.")
 if password!=confirm_password:return page(request,"auth.html",db,mode="register",error="Your passwords do not match.")
 if db.query(User).filter((User.username==username)|(User.email==email)).first():return page(request,"auth.html",db,mode="register",error="That username or email is already registered.")
 db.add(User(username=username,email=email,password_hash=hash_password(password)));db.commit()
 return RedirectResponse("/login?registered=1",303)
@app.get("/login",response_class=HTMLResponse)
def login_page(request:Request,db:Session=Depends(get_db)):return page(request,"auth.html",db,mode="login",registered=request.query_params.get("registered"))
@app.post("/login")
def login(request:Request,identity:str=Form(...),password:str=Form(...),db:Session=Depends(get_db)):
 u=db.query(User).filter((User.username==identity.strip())|(User.email==identity.strip().lower())).first()
 if not u or not verify_password(password,u.password_hash):return page(request,"auth.html",db,mode="login",error="The username/email or password is incorrect.")
 r=RedirectResponse("/dashboard",303);r.set_cookie("access_token",token_for(u),httponly=True,samesite="lax",secure=os.getenv("COOKIE_SECURE","false").lower()=="true",max_age=EXPIRE*60);return r
@app.get("/logout")
def logout():
 r=RedirectResponse("/",303);r.delete_cookie("access_token");return r
@app.post("/token")
def token(identity:str=Form(...),password:str=Form(...),db:Session=Depends(get_db)):
 u=db.query(User).filter((User.username==identity)|(User.email==identity.lower())).first()
 if not u or not verify_password(password,u.password_hash):raise HTTPException(401,"Incorrect login")
 return {"access_token":token_for(u),"token_type":"bearer"}
@app.get("/session-info")
def session_info(request:Request,db:Session=Depends(get_db)):
 u=current_user(request,db);return {"authenticated":bool(u),"user_id":u.id if u else None,"username":u.username if u else None}
@app.get("/session-data")
def session_data(request:Request,db:Session=Depends(get_db)):
 u=current_user(request,db);return {"authenticated":bool(u),"user":{"id":u.id,"username":u.username,"email":u.email} if u else None}

def required(request,db):
 u=current_user(request,db)
 if not u:raise HTTPException(303,headers={"Location":"/login"})
 return u
@app.get("/dashboard",response_class=HTMLResponse)
def dashboard(request:Request,db:Session=Depends(get_db)):
 u=required(request,db);items=db.query(Recommendation).filter_by(user_id=u.id).order_by(Recommendation.created_at.desc()).limit(4).all()
 return page(request,"dashboard.html",db,recent=[{**json.loads(x.result_data),"id":x.id,"planner_type":x.planner_type,"created_at":x.created_at} for x in items])

FORMS={"home":{"title":"Home Interior Budget Planner","subtitle":"Shape a comfortable space around what you want to spend.","fields":[("budget","Total budget (?)","number","required min=1"),("rooms","Rooms (select one or more)","checks","Living Room|Bedroom|Kitchen|Dining Room|Bathroom|Other"),("lights","Number of lights","number","min=0 value=0"),("fans","Number of ceiling fans","number","min=0 value=0"),("furniture","Number of furniture pieces","number","min=0 value=0"),("style","Style","text","placeholder='Modern, minimal, traditional…'"),("requirements","Additional requirements","textarea","") ]},"party":{"title":"Party Budget Planner","subtitle":"Make the celebration memorable and keep the spending clear.","fields":[("budget","Total budget (?)","number","required min=1"),("guests","Number of guests","number","required min=1"),("event_type","Event type","select","Birthday|Wedding|Corporate|Anniversary|Engagement|Other"),("venue","Venue type","select","Home|Hall|Restaurant|Outdoor|Hotel|Other"),("needs","Party needs","checks","Catering|Decoration|Entertainment"),("requirements","Additional requirements","textarea","")]},"jewelry":{"title":"Jewelry Planner","subtitle":"Find a coordinated look for your occasion and budget.","fields":[("budget","Total budget (?)","number","required min=1"),("occasion","Occasion","select","Wedding|Birthday|Party|Engagement|Festival|Casual|Corporate|Other"),("style","Style preference","select","Traditional|Modern|Minimal|Elegant|Statement|Vintage|Other"),("requirements","Additional preferences","textarea","")]}}
@app.get("/{kind}-planner",response_class=HTMLResponse)
def planner(request:Request,kind:str,db:Session=Depends(get_db)):
 if kind not in FORMS:raise HTTPException(404)
 required(request,db);return page(request,"planner.html",db,kind=kind,form=FORMS[kind])

def collect(kind,form):
 out={k:v for k,v in form.items() if k not in {"csrf","rooms","needs"}}
 if kind=="home":out["rooms"]=form.getlist("rooms")
 if kind=="party":out["needs"]=form.getlist("needs")
 try:
  b=int(out.get("budget",0));assert 0<b<=100000000
  for k in ("guests","lights","fans","furniture"):
   if k in out:assert (1<=int(out[k])<=10000 if k=="guests" else 0<=int(out[k])<=10000)
  if kind=="home" and not out.get("rooms"):raise ValueError("Choose at least one room.")
  if kind=="party" and not all(out.get(k) for k in ("event_type","venue")):raise ValueError("Select an event and venue type.")
 except (ValueError,AssertionError):raise ValueError("Enter a valid budget and quantities. Budget must be above zero; counts cannot be negative.")
 return out
async def generate(request,kind,db):
 u=required(request,db);form=await request.form();data=collect(kind,form)
 try:
  image_path=None
  if kind=="jewelry":
   upload=form.get("outfit_image")
   if upload is not None and getattr(upload,"filename",""):
    ext=Path(upload.filename).suffix.lower();allowed={".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".webp":"image/webp"}
    if ext not in allowed:raise ValueError("Upload a JPG, PNG, or WEBP image.")
    content=await upload.read(int(os.getenv("MAX_UPLOAD_MB","5"))*1024*1024+1)
    if len(content)>int(os.getenv("MAX_UPLOAD_MB","5"))*1024*1024:raise ValueError("Image must be 5 MB or smaller.")
    from PIL import Image
    import io
    try:im=Image.open(io.BytesIO(content));im.verify()
    except Exception:raise ValueError("The uploaded file is not a valid image.")
    if im.format not in ("JPEG","PNG","WEBP") or {".jpg":"JPEG",".jpeg":"JPEG",".png":"PNG",".webp":"WEBP"}.get(ext)!=im.format:raise ValueError("The file extension does not match a supported image format.")
    image_path=str(UPLOAD/(secrets.token_hex(16)+ext));Path(image_path).write_bytes(content);data["image_path"]=image_path
  result={"home":generate_home_plan,"party":generate_party_plan,"jewelry":generate_jewelry_plan}[kind](data)
  rec=Recommendation(user_id=u.id,planner_type=kind,input_data=json.dumps(data),result_data=json.dumps(result));db.add(rec);db.commit();db.refresh(rec)
  return RedirectResponse(f"/recommendation/{rec.id}",303)
 except AIServiceError as e:return page(request,"planner.html",db,kind=kind,form=FORMS[kind],error=str(e))
 except ValueError as e:return page(request,"planner.html",db,kind=kind,form=FORMS[kind],error=str(e))
@app.post("/generate-home")
async def gen_home(request:Request,db:Session=Depends(get_db)):return await generate(request,"home",db)
@app.post("/generate-party")
async def gen_party(request:Request,db:Session=Depends(get_db)):return await generate(request,"party",db)
@app.post("/generate-jewelry")
async def gen_jewelry(request:Request,db:Session=Depends(get_db)):return await generate(request,"jewelry",db)

@app.get("/history",response_class=HTMLResponse)
def history(request:Request,db:Session=Depends(get_db)):
 u=required(request,db);rows=db.query(Recommendation).filter_by(user_id=u.id).order_by(Recommendation.created_at.desc()).all()
 return page(request,"history.html",db,rows=[{"id":x.id,"kind":x.planner_type,"date":x.created_at,"result":json.loads(x.result_data)} for x in rows])
@app.post("/recommendation/{rid}/delete")
def delete_recommendation(rid:int,request:Request,db:Session=Depends(get_db)):
 u=required(request,db);row=db.query(Recommendation).filter_by(id=rid,user_id=u.id).first()
 if not row:raise HTTPException(404)
 db.delete(row);db.commit();return RedirectResponse("/history",303)
@app.get("/recommendation/{rid}",response_class=HTMLResponse)
def detail(rid:int,request:Request,db:Session=Depends(get_db)):
 u=required(request,db);row=db.query(Recommendation).filter_by(id=rid,user_id=u.id).first()
 if not row:raise HTTPException(404)
 return page(request,"detail.html",db,row=row,result=json.loads(row.result_data),data=json.loads(row.input_data))












