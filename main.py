from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF

app = FastAPI()

# ⚠️ CHANGE THIS to your actual WordPress domain
origins = [
    "https://steelblue-newt-464495.hostingersite.com/",
    "https://www.steelblue-newt-464495.hostingersite.com/"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/crop/flipkart-label")
async def crop_flipkart_label(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    pdf_bytes = await file.read()

    try:
        src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not open PDF.")

    LABEL_WIDTH_PT = 4 * 72
    LABEL_HEIGHT_PT = 6 * 72

    out_doc = fitz.open()

    def get_label_rect(page):
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        # TEMP values (will tune later)
        margin_x = 15
        label_height = page_height * 0.45
        label_y_bottom = page_height - label_height

        x0 = margin_x
        y0 = label_y_bottom
        x1 = page_width - margin_x
        y1 = page_height

        return fitz.Rect(x0, y0, x1, y1)

    for page_index in range(len(src_doc)):
        page = src_doc[page_index]
        label_rect = get_label_rect(page)

        if label_rect.is_empty or label_rect.height <= 0 or label_rect.width <= 0:
            continue

        new_page = out_doc.new_page(width=LABEL_WIDTH_PT, height=LABEL_HEIGHT_PT)

        src_w = label_rect.width
        src_h = label_rect.height

        scale_x = LABEL_WIDTH_PT / src_w
        scale_y = LABEL_HEIGHT_PT / src_h
        scale = min(scale_x, scale_y)

        dest_w = src_w * scale
        dest_h = src_h * scale

        dest_x0 = (LABEL_WIDTH_PT - dest_w) / 2
        dest_y0 = (LABEL_HEIGHT_PT - dest_h) / 2
        dest_x1 = dest_x0 + dest_w
        dest_y1 = dest_y0 + dest_h

        dest_rect = fitz.Rect(dest_x0, dest_y0, dest_x1, dest_y1)

        new_page.show_pdf_page(dest_rect, src_doc, page_index, clip=label_rect)

    if len(out_doc) == 0:
        raise HTTPException(status_code=400, detail="No label content found / crop rect invalid.")

    out_bytes = out_doc.write()
    out_doc.close()
    src_doc.close()

    return Response(
        content=out_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="flipkart-labels-4x6.pdf"'
        },
    )
