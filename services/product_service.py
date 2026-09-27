from urllib.parse import quote_plus
PLATFORMS={"amazon":"https://www.amazon.in/s?k={}","flipkart":"https://www.flipkart.com/search?q={}","ikea":"https://www.ikea.com/in/en/search/?q={}","swiggy":"https://www.swiggy.com/search?query={}","zomato":"https://www.zomato.com/india/search?q={}","oyo":"https://www.oyorooms.com/search?location={}"}
def search_url(item,platform="amazon"):
 return PLATFORMS.get(platform.lower(),PLATFORMS["amazon"]).format(quote_plus(item))
