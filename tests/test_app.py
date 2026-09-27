import os
os.environ["MOCK_AI"]="true"
os.environ["SECRET_KEY"]="test-secret-key-with-at-least-32-characters"
from fastapi.testclient import TestClient
from main import app

def test_landing_and_protected_redirect():
 with TestClient(app) as c:
  assert c.get("/").status_code==200
  r=c.get("/dashboard",follow_redirects=False);assert r.status_code==303

def test_register_login_and_history(tmp_path):
 # Uses the default local database; unique identity per test invocation.
 with TestClient(app) as c:
  name="user"+os.urandom(3).hex()
  r=c.post("/register",data={"username":name,"email":name+"@example.com","password":"secret12345","confirm_password":"secret12345"},follow_redirects=False)
  assert r.status_code==303
  r=c.post("/login",data={"identity":name,"password":"secret12345"},follow_redirects=False)
  assert r.status_code==303 and "access_token" in r.cookies
  assert c.get("/dashboard").status_code==200
  assert c.get("/history").status_code==200

def test_invalid_credentials_and_form():
 with TestClient(app) as c:
  assert c.post("/login",data={"identity":"nobody","password":"bad"}).status_code==200
  r=c.post("/generate-home",data={"budget":"-2","rooms":"Bedroom"},follow_redirects=False)
  assert r.status_code in (303,200)

def test_planner_and_budget_math():
 with TestClient(app) as c:
  name="user"+os.urandom(3).hex();c.post("/register",data={"username":name,"email":name+"@example.com","password":"secret12345","confirm_password":"secret12345"});c.post("/login",data={"identity":name,"password":"secret12345"})
  r=c.post("/generate-party",data={"budget":"50000","guests":"35","event_type":"Birthday","venue":"Home","needs":"Catering"},follow_redirects=False)
  assert r.status_code==303
  detail=c.get(r.headers["location"]);assert detail.status_code==200 and "Remaining budget" in detail.text

def test_missing_recommendation():
 with TestClient(app) as c:
  name="user"+os.urandom(3).hex();c.post("/register",data={"username":name,"email":name+"@example.com","password":"secret12345","confirm_password":"secret12345"});c.post("/login",data={"identity":name,"password":"secret12345"})
  assert c.get("/recommendation/999999").status_code==404

def create_user(c):
 name="owner"+os.urandom(4).hex()
 c.post("/register",data={"username":name,"email":name+"@example.com","password":"secret12345","confirm_password":"secret12345"})
 c.post("/login",data={"identity":name,"password":"secret12345"})
 return name

def test_logout_and_session_safety():
 with TestClient(app) as c:
  name=create_user(c)
  data=c.get("/session-data").json()
  assert data["authenticated"] and data["user"]["username"]==name
  assert "password_hash" not in str(data)
  c.get("/logout")
  assert c.get("/session-info").json()["authenticated"] is False

def test_home_and_jewelry_generators_save_history():
 with TestClient(app) as c:
  create_user(c)
  home=c.post("/generate-home",data={"budget":"90000","rooms":"Living Room","rooms":"Bedroom","lights":"4","fans":"2","furniture":"3","style":"Modern"},follow_redirects=False)
  assert home.status_code==303
  jewelry=c.post("/generate-jewelry",data={"budget":"15000","occasion":"Wedding","style":"Elegant"},follow_redirects=False)
  assert jewelry.status_code==303
  history=c.get("/history")
  assert history.status_code==200 and "Home plan" in history.text and "Jewelry plan" in history.text

def test_recommendations_are_private():
 with TestClient(app) as owner:
  create_user(owner)
  r=owner.post("/generate-party",data={"budget":"20000","guests":"20","event_type":"Birthday","venue":"Home"},follow_redirects=False)
  path=r.headers["location"]
 with TestClient(app) as other:
  create_user(other)
  assert other.get(path).status_code==404

