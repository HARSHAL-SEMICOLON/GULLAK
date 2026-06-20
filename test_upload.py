import requests

with open("gpay_statement_20251101_20260430.pdf", "rb") as f:
    files = {"file": ("gpay_statement_20251101_20260430.pdf", f, "application/pdf")}
    res = requests.post("http://127.0.0.1:8000/upload", files=files)
    print(res.status_code)
    print(res.text)
