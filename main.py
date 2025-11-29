from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF

app = FastAPI()

# CORS – allow all origins (simple + safe for this tool)
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,   # no cookies/credentials needed
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    LABEL_WIDTH_PT = 4 * 72
    LABEL_HEIGHT_PT = 6 * 72

    out_doc = fitz.open()

       # ---- DEFINE LABEL AREA AS PERCENTAGES OF THE PAGE ----
    # You can tweak these 4 numbers to fine-tune the crop area.
    # 0.0 = left/bottom edge, 1.0 = right/top edge of original A4 page.
    LABEL_X0_PERCENT = 0.03   # left side of label
    LABEL_Y0_PERCENT = 0.32   # bottom of label
    LABEL_X1_PERCENT = 0.63   # right side of label
    LABEL_Y1_PERCENT = 0.92   # top of label

   # -----------------------------
# LABEL CROP CONFIG (TUNE HERE)
# -----------------------------
# 0.0 = left / top edge of original page
# 1.0 = right / bottom edge of original page
# These values are tuned to the red-box label you showed in Paint.
LABEL_X0_PERCENT = 0.32   # left edge of label
LABEL_X1_PERCENT = 0.68   # right edge of label
LABEL_Y0_PERCENT = 0.07   # top edge of label
LABEL_Y1_PERCENT = 0.49   # bottom edge of label


def get_label_rect(page):
    """
    Return the rectangle (in page coordinates) that contains ONLY the shipping label.
    Adjust the four LABEL_*_PERCENT constants above to fine-tune.
    """
    page_rect = page.rect
    page_width = page_rect.width
    page_height = page_rect.height

    # In PyMuPDF, (0,0) is TOP-LEFT and y increases downwards.
    x0 = page_width  * LABEL_X0_PERCENT
    y0 = page_height * LABEL_Y0_PERCENT
    x1 = page_width  * LABEL_X1_PERCENT
    y1 = page_height * LABEL_Y1_PERCENT

    return fitz.Rect(x0, y0, x1, y1)


    # Process each page
    for page_index in range(len(src_doc)):
        page = src_doc[page_index]
        label_rect = get_label_rect(page)

        if label_rect.is_empty or label_rect.height <= 0 or label_rect.width <= 0:
            continue

        new_page = out_doc.new_page(width=LABEL_WIDTH_PT, height=LABEL_HEIGHT_PT)

        src_w = label_rect.width
        src_h = label_rect.height

        # Scale uniformly to fit inside 4×6
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
