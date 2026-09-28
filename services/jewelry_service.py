from services.recommendation_service import make_plan
def generate_jewelry_plan(data,provider=None):
 r=make_plan("jewelry",data,provider)
 r["outfit_analysis"]="Your outfit image was uploaded securely. Image analysis is unavailable until a vision provider is integrated." if data.get("image_path") else "No outfit image provided. Recommendations use your occasion and style preferences."
 return r
