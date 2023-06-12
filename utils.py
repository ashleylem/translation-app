import io
import os
import openai
import docx
import cv2
from cv2 import imdecode
from itertools import groupby
import subprocess
from io import BytesIO
from flask import Flask, request, send_file, send_from_directory, render_template,  url_for, flash, redirect, jsonify, session
from werkzeug.utils import secure_filename
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Inches
import pytesseract
from PIL import Image
from datetime import datetime
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, current_user, set_access_cookies, get_jwt_identity
import calendar
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from models import User, db
from utils import *
import uuid
import numpy as np


def extract_grouped_text(ocr_data):
    dpi = 300
    tolerance = dpi // 10

    lines = group_words_to_lines(ocr_data, tolerance)
    blocks = group_lines_to_blocks(lines, tolerance)
    formatted_text = ""

    for block in blocks:
        for line in block:
            text = ' '.join([str(word.get('text', '')) for word in line])
            formatted_text += text + '\n'
        formatted_text += '\n'

    return formatted_text


def group_words_to_lines(ocr_data, tolerance):

    words = [
        {
            "text": ocr_data["text"][i],
            "left": float(ocr_data["left"][i]),
            "top": float(ocr_data["top"][i]),
            "height": float(ocr_data["height"][i]),
        }
        for i in range(len(ocr_data["text"]))
        if ocr_data["text"][i].strip()
    ]

    line_groups = groupby(
        sorted(words, key=lambda word: word["top"]),
        key=lambda word: find_nearest(word["top"], words, tolerance),
    )
    lines = [[word for word in words] for _, words in line_groups]

    return lines


def find_nearest(value, candidates, tolerance):
    distances = [abs(candidate["top"] - value) for candidate in candidates]
    min_distance = min(distances)
    if min_distance <= tolerance:
        return candidates[distances.index(min_distance)]
    else:
        print(f"No matching candidate found for {value}")
        return None


def group_lines_to_blocks(lines, tolerance):
    blocks = []
    current_block = []
    for line in lines:
        if not current_block:
            current_block.append(line)
            current_x = np.mean([float(word['left']) for word in line if isinstance(
                word['left'], str) and word['left'].replace('.', '', 1).isdigit()])

        else:
            x = np.mean([float(word['left']) for word in line if isinstance(
                word['left'], str) and word['left'].replace('.', '', 1).isdigit()])
            if abs(x - current_x) <= tolerance:
                current_block.append(line)
            else:
                blocks.append(current_block)
                current_block = [line]
                current_x = x

    if current_block:
        blocks.append(current_block)

    return blocks


def image_to_docx(file_stream, target_language, source_language, translator_name):
    ocr_data = ocr_image(file_stream)
    if not any(text.strip() for text in ocr_data["text"]):
        raise ValueError("No text detected in the image file")

    grouped_text = extract_grouped_text(ocr_data)
    translated_text = translate_text(
        grouped_text, source_language, target_language, max_tokens_per_chunk=1000)

    doc = docx.Document()

    # ...

    # Add the translated text to the Word document
    for paragraph_text in translated_text.split('\n'):
        paragraph = doc.add_paragraph(paragraph_text)
        for run in paragraph.runs:
            run.font.name = 'Calibri'
            run.font.size = Pt(12)
        paragraph.paragraph_format.space_before = Pt(6)
        paragraph.paragraph_format.space_after = Pt(6)
    currentDay = datetime.now().day
    currentMonth = datetime.now().month
    currentYear = datetime.now().year
    month_name = calendar.month_name[currentMonth]

    standard_text = f"""CERTIFICATION OF TRANSLATOR'S COMPETENCE
    
I, {translator_name}, hereby certify that the above is an accurate translation of the original Birth Certificate in Spanish, and that I am competent in both English and Spanish to render such translation.

_______________________________________
Translator’s Signature

Immigration Law Office of
Theodore Texidor, Esq.
8095 NW 12th Street Ste. 105
Doral, Florida 33126
State of Florida, County of Miami Dade

Affiant personally known to me    
Sworn before me, this {currentDay}th day of {month_name} {currentYear}

_____________________________________________
Notary Public"""

    for index, line in enumerate(standard_text.split('\n')):
        paragraph = doc.add_paragraph()

        # Apply formatting to the run (text)
        run = paragraph.add_run(line)
        run.font.name = 'Cambria'
        run.font.size = Pt(12)

        # Apply formatting to the paragraph
        paragraph_format = paragraph.paragraph_format
        paragraph_format.space_before = Pt(1)
        paragraph_format.space_after = Pt(1)

        if index == 0:  # First line
            run.font.bold = True
            run.font.size = Pt(14)
            paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif index in [4, 5, 6]:
            paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        elif index in list(range(7, 12)):
            paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run.font.size = Pt(9)
        else:
            paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    output_stream = io.BytesIO()
    doc.save(output_stream)
    output_stream.seek(0)
    return output_stream



def ocr_image(file):
    # Convert the file object to a NumPy array
    file_bytes = np.asarray(bytearray(file.read()), dtype=np.uint8)

    # Reset the file object's position to the beginning
    file.seek(0)

    # Decode the file bytes to an OpenCV image
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Apply a median blur to reduce noise
    dilation = cv2.dilate(gray, np.ones((1,1)))
    # opened = cv2.morphologyEx(gray, cv2.MORPH_OPEN, np.ones((1, 1), np.uint8))
    # eroding = cv2.morphologyEx(gray, cv2.MORPH_ERODE, np.ones((1, 1)))
    closing = cv2.morphologyEx(
        dilation, cv2.MORPH_CLOSE,  np.ones((1, 1), np.uint8))
   


    # Apply adaptive thresholding
    _, new_img = cv2.threshold(
        closing, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Convert the OpenCV image (NumPy array) to a PIL Image
    pil_img = Image.fromarray(new_img)

    # Save the preprocessed image as a JPEG using PIL
    pil_img.save('preprocessed_image.jpg', 'JPEG')

    # Perform OCR
    data = pytesseract.image_to_data(
        new_img, config="--psm 3", lang='spa', output_type=pytesseract.Output.DICT)
    return data


def translate_text(source_text, source_lang, target_lang, max_tokens_per_chunk):
    print(source_text)
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=f"Translate the following text from {source_lang} to {target_lang}: {source_text}",
        max_tokens=max_tokens_per_chunk,
        n=1,
        stop=None,
        temperature=0.5,
    )

    translated_text = response.choices[0].text.strip()
    return translated_text

