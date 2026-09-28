import os
from decimal import Decimal,InvalidOperation
from services.groq_service import generate_structured_response
from services.product_service import search_url
def money(v):
 try:x=Decimal(str(v))
 except (InvalidOperation,ValueError,TypeError):raise ValueError("AI returned an invalid amount.")
 if not x.is_finite() or x<0:raise ValueError("AI returned an invalid amount.")
 return int(x.quantize(Decimal("1")))
def make_plan(kind,data,provider=None):
 budget=money(data["budget"])
 if os.getenv("MOCK_AI","false").lower()=="true":
  specs={"home":[("Lighting","LED lighting",.12),("Furniture","Multi-purpose furniture",.34),("Decor","Textiles and decor",.12)],"party":[("Catering","Seasonal catering menu",.38),("Decoration","Reusable venue decor",.16),("Entertainment","Local event entertainment",.12)],"jewelry":[("Necklace","Versatile coordinated necklace",.24),("Earrings","Occasion earrings",.18),("Bracelet","Matching bracelet",.12)]}
  result={"recommendations":[{"category":c,"item":i,"description":"A practical planning estimate based on your budget and preferences. Not a live price.","estimated_price":max(100,int(budget*f)),"quantity":1,"platform":"Amazon"} for c,i,f in specs[kind]],"additional_suggestions":["Compare current local prices before purchasing.","Keep a small contingency for delivery, taxes, or last-minute changes."]}
 else:
  prompt=f"Create a practical {kind} plan for this user input: {data}. Budget INR {budget}. Return JSON with recommendations list (category,item,description,estimated_price,quantity,platform), additional_suggestions list. Do not exceed budget. Estimates are not live prices."
  result=generate_structured_response(prompt,provider)
  if not isinstance(result,dict) or not isinstance(result.get("recommendations"),list):raise ValueError("AI response did not match the plan format.")
 rows=[]
 for r in result.get("recommendations",[]):
  try:
   p=money(r.get("estimated_price",0));q=int(r.get("quantity",1))
   if q<1:continue
  except (ValueError,TypeError,AttributeError):continue
  row={"category":str(r.get("category","Other"))[:80],"item":str(r.get("item","Recommended item"))[:120],"description":str(r.get("description","Practical option for your plan."))[:500],"estimated_price":p,"quantity":q,"total_price":p*q,"platform":str(r.get("platform","Amazon"))[:40]}
  row["search_url"]=search_url(row["item"],row["platform"]);rows.append(row)
 while rows and sum(x["total_price"] for x in rows)>budget:rows.pop()
 total=sum(x["total_price"] for x in rows)
 result.update(planner=kind,currency="INR",total_budget=budget,recommendations=rows,total_estimated_cost=total,remaining_budget=budget-total)
 result["budget_allocation"]=[{"category":c,"allocated_budget":sum(x["total_price"] for x in rows if x["category"]==c)} for c in dict.fromkeys(x["category"] for x in rows)]
 result["additional_suggestions"]=[str(x)[:250] for x in result.get("additional_suggestions",[])][:8]
 return result
