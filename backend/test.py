import inspect
import playwright
from playwright.async_api import Page

print(playwright.__version__)   # should print 1.54.0
print("wait_for_response" in dir(Page))   