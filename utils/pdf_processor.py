import pdfplumber

def extract_text_with_pages(pdf_file):
    full_text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                full_text += f"\n\n--- [Page {i + 1}] ---\n\n{text}"
    return full_text
