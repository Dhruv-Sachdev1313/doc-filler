import io
import os
import re
from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from docx import Document
from dotenv import load_dotenv

import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
print(os.getenv("GEMINI_API_KEY"))

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# In-memory state (you can use Redis/session later)
SESSION = {}

# Debug endpoint to check session state (remove in production)
@app.get("/debug/session")
async def debug_session():
    return {"session_keys": list(SESSION.keys()), "session_data": SESSION}


def extract_text_from_docx(file: UploadFile) -> tuple[str, Document]:
    """Extract text and return both text and the document object"""
    # Reset file pointer to beginning
    file.file.seek(0)
    doc = Document(file.file)
    full_text = []
    for p in doc.paragraphs:
        full_text.append(p.text)
    # Also check tables for text
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                full_text.append(cell.text)
    return "\n".join(full_text), doc


def extract_placeholders(text: str):
    patterns = [
        r"\[[^\]]+\]",
        r"\$?\[[_.\s]*\]",
        r"\{[^\}]+\}",
        r"<[^>]+>",
    ]
    placeholders = set()
    for pat in patterns:
        placeholders.update(re.findall(pat, text))
    return list(placeholders)


def identify_placeholders_with_llm(text: str, placeholders: list):
    """
    Use Gemini to identify what each placeholder means in context.
    """
    snippets = {}
    for ph in placeholders:
        for match in re.finditer(re.escape(ph), text):
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            snippets[ph] = text[start:end]

    prompt = f"""
You are a legal document analyzer. For each placeholder, describe what the user should fill in.

Return **valid JSON only** in this format whaich would be passed to `json.loads()`:
[
  {{"placeholder": "...", "label": "...", "question": "..."}}
]

Snippets:
{snippets}
"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        print(response.text)
        
        import json
        data = json.loads(response.text.removeprefix("```json").removesuffix("```").strip())
    except Exception as e:
        print(f"Error with Gemini API: {e}")
        # Fallback if API call or parsing fails
        data = [
            {"placeholder": ph, "label": ph, "question": f"What should I fill for {ph}?"}
            for ph in placeholders
        ]

    return data


def replace_placeholders_in_document(doc: Document, answers: dict):
    """
    Replace placeholders in document while preserving formatting.
    This function modifies paragraphs and table cells in place.
    """
    # Replace in paragraphs
    for paragraph in doc.paragraphs:
        for placeholder, answer in answers.items():
            if placeholder in paragraph.text:
                # Replace text while preserving formatting
                replace_text_in_paragraph(paragraph, placeholder, answer)
    
    # Replace in tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for placeholder, answer in answers.items():
                        if placeholder in paragraph.text:
                            replace_text_in_paragraph(paragraph, placeholder, answer)


def replace_text_in_paragraph(paragraph, old_text, new_text):
    """
    Replace text in a paragraph while preserving formatting.
    This handles cases where the placeholder might span multiple runs.
    """
    if old_text not in paragraph.text:
        return
    
    # Get all runs in the paragraph
    runs = paragraph.runs
    
    # Build full text and track run boundaries
    full_text = ""
    run_boundaries = []
    for run in runs:
        start = len(full_text)
        full_text += run.text
        end = len(full_text)
        run_boundaries.append((start, end, run))
    
    # Find placeholder positions
    start_pos = full_text.find(old_text)
    if start_pos == -1:
        return
    
    end_pos = start_pos + len(old_text)
    
    # Clear all run texts first
    for _, _, run in run_boundaries:
        run.text = ""
    
    # Rebuild text with replacement
    new_full_text = full_text.replace(old_text, new_text)
    
    # Put the new text in the first run to preserve some formatting
    if runs:
        runs[0].text = new_full_text


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile):
    text, doc = extract_text_from_docx(file)
    placeholders = extract_placeholders(text)
    details = identify_placeholders_with_llm(text, placeholders)

    SESSION["text"] = text
    SESSION["doc"] = doc  # Store the original document object
    SESSION["placeholders"] = details
    SESSION["answers"] = {}
    SESSION["file_name"] = file.filename

    first_q = details[0]["question"] if details else "No placeholders found."
    total_questions = len(details)
    progress_percentage = round((0 + 1) / total_questions * 100, 1) if total_questions > 0 else 0
    
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request, 
            "index": 0, 
            "question": first_q, 
            "total_questions": total_questions,
            "progress_percentage": progress_percentage
        },
    )


@app.post("/fill", response_class=HTMLResponse)
async def fill(
    request: Request,
    answer: str = Form(...),
    index: int = Form(...)
):
    details = SESSION["placeholders"]
    SESSION["answers"][details[index]["placeholder"]] = answer

    index += 1
    if index < len(details):
        next_q = details[index]["question"]
        total_questions = len(details)
        progress_percentage = round((index + 1) / total_questions * 100, 1)
        
        return templates.TemplateResponse(
            "chat.html",
            {
                "request": request, 
                "index": index, 
                "question": next_q, 
                "total_questions": total_questions,
                "progress_percentage": progress_percentage,
                "show_confirmation": True
            }
        )
    else:
        # All questions completed - render completion page
        return templates.TemplateResponse(
            "complete.html",
            {
                "request": request,
                "filename": SESSION.get("file_name", "Unknown"),
                "total_fields": len(SESSION.get("placeholders", [])),
                "processing_time": "Less than 1 minute",
            },
        )


@app.get("/download")
async def download():
    # Check if session has required data
    if "text" not in SESSION:
        return HTMLResponse(
            content="<h2>Error: No document data found</h2><p>Please upload and fill a document first.</p><a href='/'>Go back to upload</a>",
            status_code=400
        )
    
    if "answers" not in SESSION:
        return HTMLResponse(
            content="<h2>Error: No answers found</h2><p>Please complete the form filling process first.</p><a href='/'>Go back to upload</a>",
            status_code=400
        )
    
    if "doc" not in SESSION:
        return HTMLResponse(
            content="<h2>Error: Original document not found</h2><p>Please upload a document first.</p><a href='/'>Go back to upload</a>",
            status_code=400
        )
    
    try:
        # Get the original document and answers
        original_doc = SESSION["doc"]
        answers = SESSION["answers"]
        file_name = SESSION.get("file_name", "document.docx")
        
        # Create a deep copy of the document by saving and reloading it
        # This ensures we don't modify the original stored document
        temp_buffer = io.BytesIO()
        original_doc.save(temp_buffer)
        temp_buffer.seek(0)
        
        # Create a new document from the saved buffer
        doc = Document(temp_buffer)
        
        # Replace placeholders in the document while preserving formatting
        replace_placeholders_in_document(doc, answers)
        
        # Save the final document to BytesIO
        output = io.BytesIO()
        doc.save(output)
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename=filled_{file_name}",
                "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            }
        )
        
    except Exception as e:
        return HTMLResponse(
            content=f"<h2>Error creating document</h2><p>An error occurred: {str(e)}</p><a href='/'>Go back to upload</a>",
            status_code=500
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
