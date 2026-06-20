# pyrefly: ignore [missing-import]
import pdfplumber

def extract_text_sample(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:3]):
            print(f"--- Page {i+1} ---")
            text = page.extract_text()
            if text:
                print(text[:1000].encode('utf-8', 'replace').decode('utf-8'))
            else:
                print("No text found")

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    extract_text_sample("gpay_statement_20251101_20260430.pdf")
