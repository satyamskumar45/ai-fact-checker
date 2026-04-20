from PyPDF2 import PdfReader


def extract_text_from_pdf(file):
    """Extract and return all readable text from an uploaded PDF file."""
    try:
        reader = PdfReader(file)
        pages_text = []

        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages_text.append(page_text.strip())

        return "\n\n".join(pages_text)
    except Exception as error:
        return f""
