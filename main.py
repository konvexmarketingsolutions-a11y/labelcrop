from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF

app = FastAPI()

# CORS – allow all origins (simple for now)
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# LABEL CROP CONFIG (tune these four numbers only)
# -------------------------------------------------
# 0.0 = left / top edge of original page
# 1.0 = right / bottom edge of original page
# Start with these; we can tweak after it's returning a valid PDF.
LABEL_X0_PERCENT = 0.30   # left edge of label
LABEL_X1_PERCENT = 0.70   # right edge of label
LABEL_Y0_PERCENT = 0.08   # top edge of label
LABEL_Y1_PERCENT = 0.52   # bottom edge of label


def get_label_rect(page: fitz.Page) -> fitz.Rect:
    """
    Return the rectangle (page coordinates) that contains ONLY the shipping label.
    PyMuPDF: page.rect = (0, 0, width, height) with origin at TOP-LEFT, y downwards.
    """
    page_rect = page.rect
    page_width = page_rect.width
    page_height = page_rect.height

    x0 = page_width * LABEL_X0_PERCENT
    y0 = page_height * LABEL_Y0_PERCENT
    x1 = page_width * LABEL_X1_PERCENT
    y1 = page_height * LABEL_Y1_PERCENT

    # Clamp inside page
    x0 = max(0, min(x0, page_width))
    x1 = max(0, min(x1, page_width))
    y0 = max(0, min(y0, page_height))
    y1 = max(0, min(y1, page_height))

    if x1 <= x0 or y1 <= y0:
        return fitz.Rect(0, 0, 0, 0)

    return fitz.Rect(x0, y0, x1, y1)


@app.post("/crop/flipkart-label")
async def crop_flipkart_label(file: UploadFile = File(...)):
    # Only accept PDF files
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    pdf_bytes = await file.read()

    try:
        src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not open PDF.")

    # 4×6 inches in PDF points (1 inch = 72 pt)
    LABEL_WIDTH_PT = 4 * 72   # 288
    LABEL_HEIGHT_PT = 6 * 72  # 432

    out_doc = fitz.open()
    pages_added = 0

    for page_index in range(len(src_doc)):
        page = src_doc[page_index]
        label_rect = get_label_rect(page)

        if label_rect.is_empty or label_rect.width <= 0 or label_rect.height <= 0:
            continue

        # New 4×6 page
        new_page = out_doc.new_page(width=LABEL_WIDTH_PT, height=LABEL_HEIGHT_PT)

        src_w = label_rect.width
        src_h = label_rect.height

        # Scale uniformly so label fits inside 4×6
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
        pages_added += 1

    # If nothing could be cropped, just return the ORIGINAL PDF
    if pages_added == 0:
        src_doc.close()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="flipkart-labels-original.pdf"'
            },
        )

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
