import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import json

st.set_page_config(page_title="Vinted Link Image Generator", layout="centered")

DARK_CSS = """
<style>
.stApp { background-color: #12161c; color: #f2f2f2; }
</style>
"""
LIGHT_CSS = """
<style>
.stApp { background-color: #ffffff; color: #111111; }
</style>
"""

BG_COLORS = {
    "Red": (214, 69, 69),
    "Blue": (62, 111, 166),
    "Green": (60, 140, 93),
    "Pink": (214, 119, 154),
    "Purple": (139, 95, 191),
}

st.title("Vinted Link Image Generator")

theme = st.radio("Select Theme", ["Dark Mode", "Light Mode"], horizontal=False)
st.markdown(DARK_CSS if theme == "Dark Mode" else LIGHT_CSS, unsafe_allow_html=True)

remove_bg = st.toggle("Remove Background", value=True)

mode = st.radio("Choose Mode", ["Single URL", "Bulk URLs"])

bg_color_name = st.selectbox("Select Background Color", list(BG_COLORS.keys()))

if mode == "Single URL":
    url_input = st.text_input("Paste Vinted URL")
    urls = [url_input.strip()] if url_input.strip() else []
else:
    bulk_input = st.text_area("Paste Vinted URLs (one per line)")
    urls = [u.strip() for u in bulk_input.splitlines() if u.strip()]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_listing(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=12)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    data = {"title": "", "price": "", "details": "", "image_url": ""}

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string)
        except Exception:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            candidates = item.get("@graph", [item]) if isinstance(item, dict) else [item]
            for prod in candidates:
                if not isinstance(prod, dict) or prod.get("@type") != "Product":
                    continue
                data["title"] = data["title"] or prod.get("name", "")
                img = prod.get("image")
                if isinstance(img, list):
                    img = img[0] if img else ""
                data["image_url"] = data["image_url"] or img or ""
                offers = prod.get("offers")
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                if isinstance(offers, dict) and offers.get("price"):
                    data["price"] = data["price"] or str(offers["price"])
                brand = prod.get("brand")
                if isinstance(brand, dict):
                    data["details"] = data["details"] or brand.get("name", "")

    if not data["image_url"]:
        og_img = soup.find("meta", property="og:image")
        if og_img:
            data["image_url"] = og_img.get("content", "")
    if not data["title"]:
        og_title = soup.find("meta", property="og:title")
        data["title"] = (og_title.get("content") if og_title else "") or (soup.title.string if soup.title else "")

    return data


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def remove_background(img: Image.Image) -> Image.Image:
    from rembg import remove
    return remove(img)


def build_card(photo: Image.Image | None, title: str, details: str, price: str, bg_rgb: tuple) -> Image.Image:
    W, H = 800, 1000
    top_h = 650
    card = Image.new("RGB", (W, H), (18, 24, 21))
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, 0, W, top_h], fill=bg_rgb)

    if photo:
        photo = photo.convert("RGBA")
        ratio = min((W - 100) / photo.width, (top_h - 100) / photo.height)
        iw, ih = max(1, int(photo.width * ratio)), max(1, int(photo.height * ratio))
        resized = photo.resize((iw, ih))
        card.paste(resized, ((W - iw) // 2, (top_h - ih) // 2), resized)
    else:
        font = get_font(20)
        draw.text((W // 2, top_h // 2), "Image unavailable", font=font, fill=(255, 255, 255), anchor="mm")

    draw.rectangle([0, top_h, W, top_h + 64], fill=(47, 143, 91))
    draw.text((32, top_h + 32), "SOLD", font=get_font(26, bold=True), fill=(243, 239, 228), anchor="lm")

    y = top_h + 64 + 40
    draw.text((32, y), title or "Item title", font=get_font(28, bold=True), fill=(243, 239, 228))
    y += 42
    if details:
        draw.text((32, y), details, font=get_font(18), fill=(200, 196, 186))
        y += 34
    if price:
        draw.text((32, y), price, font=get_font(26, bold=True), fill=(243, 239, 228))

    return card


st.markdown("---")

if st.button("Generate Image"):
    if not urls:
        st.error("Paste a Vinted URL first.")
    for u in urls:
        st.markdown(f"**{u}**")
        with st.spinner("Fetching listing..."):
            try:
                data = fetch_listing(u)
            except Exception as e:
                st.error(
                    "Couldn't fetch this listing automatically — Vinted may be blocking the request. "
                    f"({e})"
                )
                continue

            photo = None
            if data["image_url"]:
                try:
                    img_resp = requests.get(data["image_url"], headers=HEADERS, timeout=12)
                    photo = Image.open(BytesIO(img_resp.content))
                except Exception:
                    photo = None

            if remove_bg and photo:
                try:
                    with st.spinner("Removing background..."):
                        photo = remove_background(photo)
                except Exception:
                    st.warning("Background removal failed — showing the original photo instead.")

            card = build_card(photo, data["title"], data["details"], data["price"], BG_COLORS[bg_color_name])
            st.image(card)

            buf = BytesIO()
            card.save(buf, format="PNG")
            st.download_button(
                "Download image",
                data=buf.getvalue(),
                file_name="sold.png",
                mime="image/png",
                key=f"dl_{u}",
            )
